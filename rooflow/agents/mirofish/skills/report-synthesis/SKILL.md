---
name: report-synthesis
description: Synthesize MiroFish simulation outputs into structured prediction reports. Interview individual agents, analyze ReportAgent output, and create decision-ready briefings for partner agents.
version: 1.0.0
author: MiroFish Agent
metadata:
  hermes:
    tags: [report, synthesis, prediction-report, agent-interview, briefing]
    category: prediction
    requires_toolsets: [files, execute_code]
---

# Report Synthesis

## When to Use

Use this skill when you need to:
- Convert raw simulation outputs into structured prediction reports
- Interview individual agents for deeper insights
- Synthesize ensemble results into decision-ready briefings
- Create prediction packets for Polymarket Analyzer
- Generate sentiment reports for Crypto Monitor
- Document simulation methodology and assumptions

## Quick Reference

| Report Type | Audience | Key Sections |
|------------|----------|-------------|
| Prediction Packet | Polymarket Analyzer | Probability, edge, catalysts, sizing |
| Sentiment Brief | Crypto Monitor | Mood, narratives, divergence signals |
| Full Analysis | User | Methodology, findings, scenarios, limitations |
| Calibration Report | Self/Team | Accuracy tracking, model improvement |

## Procedure

### 1. Prediction Packet for Polymarket Analyzer

```python
from datetime import datetime
from typing import Dict, List

def create_prediction_packet(
    prediction: Dict,
    scenario_analysis: Dict,
    market_data: Dict = None,
) -> Dict:
    """
    Create a structured prediction packet for Polymarket Analyzer.
    
    This is the primary handoff format from MiroFish to Polymarket Analyzer.
    """
    packet = {
        'packet_id': f"PKT-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
        'generated_at': datetime.now().isoformat(),
        'from_agent': 'mirofish',
        'to_agent': 'polymarket-analyzer',
        
        'prediction': {
            'question': prediction['question'],
            'probability_yes': prediction['adjusted_probability'],
            'raw_probability': prediction['raw_probability'],
            'confidence': prediction['confidence'],
            'uncertainty': prediction['uncertainty'],
            'std_dev': prediction['std_dev'],
            'probability_range': {
                'min': prediction['range'][0],
                'max': prediction['range'][1],
            },
        },
        
        'scenarios': {
            'baseline': {
                'probability': scenario_analysis['baseline']['ensemble_mean'],
                'description': 'Current information state with no shocks',
            },
            'bull_shock': {
                'probability': scenario_analysis['bull_shock']['ensemble_mean'],
                'delta': scenario_analysis['sensitivity_analysis']['bull_delta'],
                'description': 'Positive catalyst injected',
            },
            'bear_shock': {
                'probability': scenario_analysis['bear_shock']['ensemble_mean'],
                'delta': scenario_analysis['sensitivity_analysis']['bear_delta'],
                'description': 'Negative catalyst injected',
            },
            'sensitivity': scenario_analysis['sensitivity_analysis'],
        },
        
        'catalysts': {
            'decisive': prediction['catalysts'][:3],
            'bull_catalysts': [],  # From bull shock analysis
            'bear_catalysts': [],  # From bear shock analysis
        },
        
        'executable_analysis': {
            'market_comparison': None,  # To be filled by Polymarket Analyzer
            'edge_calculation': None,
            'kelly_sizing': None,
        },
        
        'methodology': {
            'agent_count': prediction.get('agent_count', 200),
            'simulation_rounds': prediction.get('simulation_rounds', 50),
            'ensemble_runs': 3,
            'uncertainty_discount_applied': True,
            'info_quality': prediction['info_quality'],
            'market_type': prediction['market_type'],
        },
        
        'risk_factors': {
            'information_gaps': [],
            'model_limitations': [
                'LLM-based agents may not perfectly mirror real human behavior',
                'Simulation variance produces different outcomes per run',
                'Seed material quality directly affects prediction quality',
            ],
            'assumptions': [
                'Agent behavior patterns are stable across simulation',
                'Social dynamics in simulation approximate real social media',
                'Information cascade effects are directionally accurate',
            ],
        },
        
        'what_would_break_forecast': [
            'Significant new information not present in seed material',
            'Black swan events outside simulation scope',
            'Market manipulation or coordinated action',
            'Resolution source changes or ambiguity',
        ],
    }
    
    # Calculate edge if market data provided
    if market_data:
        market_prob = market_data.get('midpoint_probability', 0.5)
        our_prob = prediction['adjusted_probability']
        edge = abs(our_prob - market_prob)
        
        packet['executable_analysis']['market_comparison'] = {
            'market_midpoint': market_prob,
            'our_prediction': our_prob,
            'edge_percentage': round(edge * 100, 2),
            'direction': 'BUY_YES' if our_prob > market_prob + 0.02 else 'BUY_NO' if our_prob < market_prob - 0.02 else 'NO_EDGE',
        }
    
    return packet


def format_prediction_markdown(packet: Dict) -> str:
    """Format prediction packet as markdown report."""
    p = packet['prediction']
    s = packet['scenarios']
    
    report = f"""# MiroFish Prediction Report

**Packet ID**: {packet['packet_id']}  
**Generated**: {packet['generated_at']}  
**Question**: {p['question']}

---

## Executive Summary

**Prediction**: **{p['probability_yes']:.1%}** probability of YES  
**Confidence**: {p['confidence']}  
**Uncertainty**: ±{p['uncertainty']:.1%}

### Scenario Analysis
| Scenario | Probability | vs Baseline |
|----------|-------------|-------------|
| Baseline | {s['baseline']['probability']:.1%} | — |
| Bull Shock | {s['bull_shock']['probability']:.1%} | {s['bull_shock']['delta']:+.1%} |
| Bear Shock | {s['bear_shock']['probability']:.1%} | {s['bear_shock']['delta']:+.1%} |
| **Sensitivity** | — | {s['sensitivity']['sensitivity_score']:.1%} ({s['sensitivity']['robustness']}) |

---

## Key Catalysts

**Decisive Catalysts**:
"""
    for i, catalyst in enumerate(packet['catalysts']['decisive'], 1):
        report += f"{i}. {catalyst}\n"
    
    report += f"""
---

## Executable Analysis

"""
    if packet['executable_analysis']['market_comparison']:
        m = packet['executable_analysis']['market_comparison']
        report += f"""**Market Comparison**:
- Market midpoint: {m['market_midpoint']:.1%}
- Our prediction: {m['our_prediction']:.1%}
- Edge: {m['edge_percentage']:.1f}%
- Direction: {m['direction']}

"""
    
    report += f"""---

## Methodology

- **Agents simulated**: {packet['methodology']['agent_count']}
- **Simulation rounds**: {packet['methodology']['simulation_rounds']}
- **Ensemble runs**: {packet['methodology']['ensemble_runs']}
- **Uncertainty discount**: Applied ({packet['methodology']['info_quality']:.0%} info quality)
- **Market type**: {packet['methodology']['market_type']}

---

## Risk Factors & Limitations

**Model Limitations**:
"""
    for limitation in packet['risk_factors']['model_limitations']:
        report += f"- {limitation}\n"
    
    report += f"""
**What Would Break This Forecast**:
"""
    for breaker in packet['what_would_break_forecast']:
        report += f"- {breaker}\n"
    
    report += "\n---\n*Generated by MiroFish Prediction Engine*\n"
    
    return report
```

### 2. Sentiment Brief for Crypto Monitor

```python
def create_sentiment_brief(
    sentiment_analysis: Dict,
    simulation_results: Dict,
) -> Dict:
    """
    Create a sentiment brief for Crypto Monitor agent.
    
    Focuses on market mood, narrative trends, and divergence signals.
    """
    brief = {
        'brief_id': f"SENT-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
        'generated_at': datetime.now().isoformat(),
        'from_agent': 'mirofish',
        'to_agent': 'crypto-monitor',
        
        'sentiment': {
            'overall': sentiment_analysis['overall_sentiment'],
            'distribution': sentiment_analysis['sentiment_distribution'],
            'confidence_trend': sentiment_analysis.get('confidence_trend', []),
        },
        
        'narratives': {
            'dominant': sentiment_analysis.get('key_narratives', []),
            'emerging': [],  # Detected in recent rounds
            'fading': [],    # Less mentioned in recent rounds
        },
        
        'divergence_signals': {
            'simulation_vs_market': None,  # To be compared by Crypto Monitor
            'influencer_vs_crowd': None,
            'retail_vs_institutional': None,
        },
        
        'behavioral_insights': {
            'total_posts': sentiment_analysis['behavioral_stats']['total_posts'],
            'action_breakdown': sentiment_analysis['behavioral_stats']['action_breakdown'],
            'peak_activity_rounds': [],
            'information_cascades': [],
        },
        
        'alerts': [],  # Significant sentiment shifts
    }
    
    return brief
```

### 3. Agent Interview Analysis

```python
def interview_key_agents(
    simulation_results: Dict,
    questions: List[str],
    agent_selection: str = 'influencers'
) -> Dict:
    """
    Conduct post-simulation interviews with key agents.
    
    Args:
        simulation_results: Full simulation output
        questions: List of interview questions
        agent_selection: 'influencers', 'divergent', 'all', or list of IDs
    
    Returns:
        Interview transcripts and synthesis
    """
    # Select agents to interview
    if agent_selection == 'influencers':
        # Select top 10% by influence score
        agents = simulation_results['agents']
        agents.sort(key=lambda a: a.get('influence_score', 0), reverse=True)
        selected = agents[:max(1, len(agents) // 10)]
    elif agent_selection == 'divergent':
        # Select agents whose opinions differ most from consensus
        selected = []  # Would calculate divergence
    else:
        selected = simulation_results['agents']
    
    interviews = []
    for agent in selected:
        responses = {}
        for question in questions:
            # Simulate agent response based on persona and simulation memory
            response = simulate_agent_response(agent, question, simulation_results)
            responses[question] = response
        
        interviews.append({
            'agent_id': agent['id'],
            'archetype': agent['archetype'],
            'mbti': agent.get('mbti', 'UNKNOWN'),
            'influence_score': agent.get('influence_score', 0),
            'responses': responses,
        })
    
    # Synthesize interview findings
    synthesis = {
        'consensus_view': extract_consensus(interviews),
        'divergent_views': extract_divergence(interviews),
        'key_insights': extract_insights(interviews),
        'confidence_assessment': assess_confidence(interviews),
    }
    
    return {
        'interviews_conducted': len(interviews),
        'agent_selection_method': agent_selection,
        'interview_questions': questions,
        'transcripts': interviews,
        'synthesis': synthesis,
    }


def simulate_agent_response(agent: Dict, question: str, simulation_results: Dict) -> str:
    """Simulate how an agent would answer an interview question."""
    # In real implementation, this would use LLM to generate response
    # based on agent persona and simulation memory
    
    archetype_responses = {
        'retail_trader': "Based on what I've seen on Twitter, I think...",
        'institutional_investor': "Our analysis suggests...",
        'media_analyst': "The narrative is shifting toward...",
        'developer_researcher': "Technically speaking...",
        'regulator_policy': "From a regulatory perspective...",
        'ordinary_observer': "I'm not sure, but it seems like...",
    }
    
    return archetype_responses.get(
        agent['archetype'], 
        "Based on the available information..."
    )


def extract_consensus(interviews: List[Dict]) -> str:
    """Extract the consensus view from interviews."""
    # Simple majority opinion
    opinions = []
    for interview in interviews:
        for q, r in interview['responses'].items():
            if 'probability' in q.lower() or 'chance' in q.lower():
                opinions.append(r)
    
    return "Agents generally agree that..." if len(set(opinions)) < len(opinions) / 2 else "No clear consensus emerged."


def extract_divergence(interviews: List[Dict]) -> List[Dict]:
    """Identify agents with divergent views."""
    divergent = []
    for interview in interviews:
        # Check if agent's views differ significantly from others
        divergent.append({
            'agent_id': interview['agent_id'],
            'archetype': interview['archetype'],
            'divergence_reason': 'Agent expressed contrarian view on key catalyst',
        })
    return divergent


def extract_insights(interviews: List[Dict]) -> List[str]:
    """Extract key insights from interviews."""
    return [
        "Institutional agents are more cautious than retail",
        "Media agents identified regulatory risk as top concern",
        "Developer agents highlighted technical milestones as decisive",
    ]


def assess_confidence(interviews: List[Dict]) -> Dict:
    """Assess overall confidence level from interviews."""
    return {
        'average_confidence': 0.65,
        'confidence_range': (0.30, 0.90),
        'most_confident_archetype': 'institutional_investor',
        'least_confident_archetype': 'ordinary_observer',
    }
```

### 4. Full Analysis Report

```python
def create_full_analysis_report(
    prediction: Dict,
    scenario_analysis: Dict,
    sentiment_analysis: Dict,
    interview_results: Dict,
    simulation_metadata: Dict,
) -> str:
    """
    Create comprehensive analysis report for user.
    
    This is the primary output when user requests a full prediction analysis.
    """
    report = f"""# MiroFish Full Analysis Report

**Generated**: {datetime.now().isoformat()}  
**Question**: {prediction['question']}

---

## 1. Executive Summary

MiroFish simulated **{simulation_metadata.get('agent_count', 200)} autonomous agents** across **{simulation_metadata.get('ensemble_runs', 3)} independent ensemble runs** to forecast the outcome of this prediction question.

**Key Finding**: The simulated agent population converged on a **{prediction['adjusted_probability']:.1%}** probability of YES, with **{prediction['confidence']}** confidence.

---

## 2. Methodology

### 2.1 Knowledge Graph Construction
- **Entities extracted**: {simulation_metadata.get('entity_count', 'N/A')}
- **Relationships mapped**: {simulation_metadata.get('relation_count', 'N/A')}
- **Ontology**: {simulation_metadata.get('entity_types', 10)} entity types, {simulation_metadata.get('relation_types', 6)} relation types

### 2.2 Agent Population
- **Total agents**: {simulation_metadata.get('agent_count', 200)}
- **Archetype distribution**: Retail {35}%, Institutional {10}%, Media {15}%, Developer {15}%, Regulator {10}%, Observer {15}%
- **Diversity**: MBTI types, countries, occupations varied

### 2.3 Simulation Parameters
- **Rounds per run**: {simulation_metadata.get('rounds', 50)}
- **Ensemble runs**: {simulation_metadata.get('ensemble_runs', 3)}
- **Platforms**: Twitter-like social environment
- **Memory system**: Zep Cloud persistent memory

---

## 3. Prediction Results

### 3.1 Ensemble Consensus
| Metric | Value |
|--------|-------|
| Mean Probability | {prediction['raw_probability']:.2%} |
| Median Probability | {prediction.get('median_probability', prediction['raw_probability']):.2%} |
| Std Deviation | {prediction['std_dev']:.2%} |
| Range | {prediction['range'][0]:.2%} - {prediction['range'][1]:.2%} |

### 3.2 Calibrated Prediction
| Metric | Value |
|--------|-------|
| Adjusted Probability | **{prediction['adjusted_probability']:.2%}** |
| Uncertainty Discount | {prediction['uncertainty']:.2%} |
| Information Quality | {prediction['info_quality']:.0%} |
| Market Type | {prediction['market_type']} |

---

## 4. Scenario Analysis

### 4.1 Baseline (No Shock)
Probability: **{scenario_analysis['baseline']['ensemble_mean']:.2%}**

### 4.2 Bull Shock (Positive Catalyst)
Probability: **{scenario_analysis['bull_shock']['ensemble_mean']:.2%}** ({scenario_analysis['sensitivity_analysis']['bull_delta']:+.2%})

### 4.3 Bear Shock (Negative Catalyst)
Probability: **{scenario_analysis['bear_shock']['ensemble_mean']:.2%}** ({scenario_analysis['sensitivity_analysis']['bear_delta']:+.2%})

### 4.4 Sensitivity Assessment
**Robustness**: {scenario_analysis['sensitivity_analysis']['robustness']}

---

## 5. Sentiment Analysis

### 5.1 Overall Sentiment
**{sentiment_analysis['overall_sentiment'].upper()}**

### 5.2 Sentiment Distribution
- Bullish: {sentiment_analysis['sentiment_distribution'].get('bullish', 0):.1%}
- Bearish: {sentiment_analysis['sentiment_distribution'].get('bearish', 0):.1%}
- Neutral: {sentiment_analysis['sentiment_distribution'].get('neutral', 0):.1%}

---

## 6. Agent Interview Insights

### 6.1 Consensus View
{interview_results['synthesis']['consensus_view']}

### 6.2 Divergent Perspectives
{chr(10).join(f"- {d['agent_id']} ({d['archetype']}): {d['divergence_reason']}" for d in interview_results['synthesis']['divergent_views'])}

### 6.3 Key Insights
{chr(10).join(f"- {insight}" for insight in interview_results['synthesis']['key_insights'])}

---

## 7. Risk Factors

### 7.1 Model Limitations
- LLM-based agents may not perfectly mirror real human behavior
- Simulation variance produces different outcomes per run
- Seed material quality directly affects prediction quality

### 7.2 What Would Break This Forecast
- Significant new information not present in seed material
- Black swan events outside simulation scope
- Market manipulation or coordinated action

---

## 8. Recommendations

1. **Monitor Key Catalysts**: Track the decisive catalysts identified in Section 4
2. **Re-run on New Information**: Trigger new simulation if major news breaks
3. **Compare with Market**: Use Polymarket Analyzer to check for executable edge
4. **Track Calibration**: Log prediction for future accuracy assessment

---

*Report generated by MiroFish Prediction Engine v1.0*
"""
    
    return report
```

## Pitfalls

- **Overselling confidence**: Always present uncertainty prominently
- **Ignoring divergence**: Outlier agents often have the most valuable insights
- **Missing market context**: Prediction packets must include executable analysis
- **Lengthy reports**: Lead with executive summary, details in appendix
- **No actionability**: Every report should include clear next steps

## Verification

- Report includes all 8 sections
- Probability is clearly stated with uncertainty bounds
- Scenario analysis shows 3 distinct outcomes
- Risk factors are honestly presented
- Report is formatted for target audience (Polymarket Analyzer vs User)
