---
name: prediction-engine
description: Generate probabilistic predictions from MiroFish simulation outputs. Apply ensemble consensus, uncertainty discounts, calibration curves, and scenario analysis (baseline, bull shock, bear shock).
version: 1.0.0
author: MiroFish Agent
metadata:
  hermes:
    tags: [prediction, probability, ensemble, uncertainty, calibration, forecasting]
    category: prediction
    requires_toolsets: [terminal, execute_code, files]
---

# Prediction Engine

## When to Use

Use this skill when you need to:
- Convert MiroFish simulation outputs into probabilistic predictions
- Run ensemble simulations and extract consensus probabilities
- Apply uncertainty discounts to raw simulation outputs
- Perform scenario stress-testing (bull/bear shocks)
- Track prediction accuracy for model calibration
- Compare simulation predictions against actual market prices

## Quick Reference

| Task | Method | Key Output |
|------|--------|-----------|
| Ensemble consensus | 3+ independent runs | Mean ± std dev probability |
| Uncertainty discount | Shrink toward 50% | Calibrated probability |
| Bull shock | Inject positive catalyst | Upside scenario probability |
| Bear shock | Inject negative catalyst | Downside scenario probability |
| Calibration tracking | Compare predictions vs outcomes | Calibration curve |
| Edge calculation | Compare vs market price | Executable edge % |

## Procedure

### 1. Ensemble Consensus Extraction

```python
import statistics
from typing import List, Dict

def extract_ensemble_consensus(
    simulation_runs: List[Dict],
    prediction_question: str
) -> Dict:
    """
    Extract consensus probability from multiple simulation runs.
    
    Args:
        simulation_runs: Results from 3+ independent MiroFish simulations
        prediction_question: The YES/NO question being predicted
    
    Returns:
        {
            'ensemble_mean': float,
            'ensemble_median': float,
            'std_dev': float,
            'min_prob': float,
            'max_prob': float,
            'individual_results': [...],
            'confidence_label': str,
        }
    """
    # Extract YES probability from each run
    probabilities = []
    individual_results = []
    
    for i, run in enumerate(simulation_runs):
        # Analyze agent opinions in final round
        final_opinions = extract_agent_opinions(run, final_round_only=True)
        
        # Calculate YES probability from agent consensus
        yes_count = sum(1 for op in final_opinions if op['prediction'] == 'YES')
        total = len(final_opinions)
        prob = yes_count / total if total > 0 else 0.5
        
        probabilities.append(prob)
        individual_results.append({
            'run_id': i + 1,
            'yes_probability': prob,
            'agent_count': total,
            'key_catalysts': extract_catalysts(run),
        })
    
    # Calculate ensemble statistics
    mean_prob = statistics.mean(probabilities)
    median_prob = statistics.median(probabilities)
    std_dev = statistics.stdev(probabilities) if len(probabilities) > 1 else 0
    
    # Confidence label
    if std_dev < 0.05:
        confidence = 'HIGH'
    elif std_dev < 0.10:
        confidence = 'MEDIUM'
    else:
        confidence = 'LOW'
    
    return {
        'ensemble_mean': round(mean_prob, 4),
        'ensemble_median': round(median_prob, 4),
        'std_dev': round(std_dev, 4),
        'min_prob': round(min(probabilities), 4),
        'max_prob': round(max(probabilities), 4),
        'individual_results': individual_results,
        'confidence_label': confidence,
    }


def extract_agent_opinions(simulation_results: Dict, final_round_only: bool = True) -> List[Dict]:
    """Extract individual agent predictions from simulation."""
    opinions = []
    
    posts = simulation_results.get('posts', [])
    
    if final_round_only:
        max_round = max(p['round'] for p in posts) if posts else 0
        posts = [p for p in posts if p['round'] == max_round]
    
    for post in posts:
        # Map sentiment to YES/NO prediction
        sentiment = post.get('sentiment', 'neutral')
        prediction = 'YES' if sentiment == 'bullish' else 'NO' if sentiment == 'bearish' else 'UNCERTAIN'
        
        opinions.append({
            'agent_id': post['author'],
            'archetype': post.get('author_archetype', 'unknown'),
            'prediction': prediction,
            'confidence': post.get('confidence', 0.5),
            'reasoning': post.get('content', ''),
        })
    
    return opinions


def extract_catalysts(simulation_results: Dict, top_n: int = 3) -> List[str]:
    """Extract top catalysts mentioned by agents."""
    # Simple keyword extraction from posts
    posts = simulation_results.get('posts', [])
    
    # In real implementation, use NLP to extract key topics
    catalysts = [
        "Regulatory announcement",
        "Major institutional entry",
        "Technical breakthrough",
        "Macroeconomic shift",
    ]
    
    return catalysts[:top_n]
```

### 2. Uncertainty Discount

```python
def apply_uncertainty_discount(
    raw_prob: float,
    std_dev: float,
    info_quality: float = 0.7,
    market_type: str = 'crypto'
) -> Dict:
    """
    Apply uncertainty haircut to raw simulation probability.
    
    Args:
        raw_prob: Raw ensemble mean probability (0-1)
        std_dev: Standard deviation across ensemble runs
        info_quality: 0.0-1.0 (1.0 = comprehensive, well-sourced)
        market_type: 'crypto', 'geopolitical', 'sports', 'policy'
    
    Returns:
        Calibrated prediction with uncertainty metrics
    """
    # Base uncertainty from simulation variance
    uncertainty = std_dev * 2.0
    
    # Adjust for information quality
    uncertainty *= (2.0 - info_quality)
    
    # Market type adjustments
    market_multipliers = {
        'crypto': 1.15,
        'geopolitical': 1.20,
        'sports': 1.30,
        'policy': 1.00,
    }
    uncertainty *= market_multipliers.get(market_type, 1.15)
    
    # Shrink toward 50% based on uncertainty
    adjusted_prob = raw_prob + (0.50 - raw_prob) * uncertainty
    
    # Bound to valid probability range
    adjusted_prob = max(0.01, min(0.99, adjusted_prob))
    
    return {
        'raw_probability': round(raw_prob, 4),
        'adjusted_probability': round(adjusted_prob, 4),
        'uncertainty': round(uncertainty, 4),
        'info_quality': info_quality,
        'market_type': market_type,
        'shrinkage': abs(raw_prob - adjusted_prob),
    }
```

### 3. Scenario Stress-Testing

```python
def run_scenario_analysis(
    base_config: Dict,
    knowledge_graph: Dict,
    prediction_question: str
) -> Dict:
    """
    Run baseline, bull shock, and bear shock simulations.
    
    Args:
        base_config: Standard simulation configuration
        knowledge_graph: Knowledge graph for agent generation
        prediction_question: The prediction question
    
    Returns:
        {
            'baseline': {...},
            'bull_shock': {...},
            'bear_shock': {...},
            'sensitivity_analysis': {...},
        }
    """
    from sentiment_simulation import OASISSimulation, configure_simulation, generate_agent_personas
    
    # Generate agents
    agents = generate_agent_personas(knowledge_graph, total_agents=200)
    
    results = {}
    
    # Baseline simulation
    print("Running baseline simulation...")
    base_sim_config = configure_simulation(agents, prediction_question, random_seed=42)
    base_sim = OASISSimulation(base_sim_config)
    base_results = base_sim.run()
    base_consensus = extract_ensemble_consensus([base_results], prediction_question)
    results['baseline'] = base_consensus
    
    # Bull shock: inject positive catalyst
    print("Running bull shock simulation...")
    bull_config = configure_simulation(agents, prediction_question, random_seed=43)
    bull_config['content']['seed_posts'].append({
        'author': 'breaking_news',
        'content': 'BREAKING: Major positive catalyst for market!',
        'timestamp': 0,
        'is_catalyst': True,
        'catalyst_type': 'bull',
    })
    bull_sim = OASISSimulation(bull_config)
    bull_results = bull_sim.run()
    bull_consensus = extract_ensemble_consensus([bull_results], prediction_question)
    results['bull_shock'] = bull_consensus
    
    # Bear shock: inject negative catalyst
    print("Running bear shock simulation...")
    bear_config = configure_simulation(agents, prediction_question, random_seed=44)
    bear_config['content']['seed_posts'].append({
        'author': 'breaking_news',
        'content': 'BREAKING: Major negative catalyst for market!',
        'timestamp': 0,
        'is_catalyst': True,
        'catalyst_type': 'bear',
    })
    bear_sim = OASISSimulation(bear_config)
    bear_results = bear_sim.run()
    bear_consensus = extract_ensemble_consensus([bear_results], prediction_question)
    results['bear_shock'] = bear_consensus
    
    # Sensitivity analysis
    base_prob = results['baseline']['ensemble_mean']
    bull_prob = results['bull_shock']['ensemble_mean']
    bear_prob = results['bear_shock']['ensemble_mean']
    
    results['sensitivity_analysis'] = {
        'bull_delta': round(bull_prob - base_prob, 4),
        'bear_delta': round(bear_prob - base_prob, 4),
        'sensitivity_score': round(max(abs(bull_prob - base_prob), abs(bear_prob - base_prob)), 4),
        'robustness': 'HIGH' if max(abs(bull_prob - base_prob), abs(bear_prob - base_prob)) < 0.15 else 'LOW',
    }
    
    return results
```

### 4. Calibration Tracking

```python
import json
import os
from datetime import datetime
from typing import List, Dict

PREDICTION_REGISTRY = '../shared-memory-bank/predictionRegistry.md'

def register_prediction(
    prediction_id: str,
    question: str,
    raw_probability: float,
    adjusted_probability: float,
    confidence: str,
    catalysts: List[str],
    source_agents: List[str],
    resolution_date: str,
) -> Dict:
    """Register a prediction for future calibration tracking."""
    
    entry = {
        'prediction_id': prediction_id,
        'timestamp': datetime.now().isoformat(),
        'question': question,
        'raw_probability': raw_probability,
        'adjusted_probability': adjusted_probability,
        'confidence': confidence,
        'catalysts': catalysts,
        'source_agents': source_agents,
        'resolution_date': resolution_date,
        'actual_outcome': None,  # To be filled later
        'accuracy': None,  # To be calculated later
    }
    
    # Append to registry
    registry_path = PREDICTION_REGISTRY
    
    # Read existing
    registry = []
    if os.path.exists(registry_path):
        with open(registry_path, 'r') as f:
            content = f.read()
            # Parse markdown table or JSON entries
            # Simplified: append JSON lines
    
    # Write entry
    with open(registry_path, 'a') as f:
        f.write(f"\n{json.dumps(entry)}\n")
    
    return entry


def calculate_calibration(
    predictions: List[Dict],
    bin_count: int = 10
) -> Dict:
    """
    Calculate calibration curve from historical predictions.
    
    Returns:
        {
            'calibration_curve': [(predicted, actual_frequency), ...],
            'brier_score': float,
            'is_well_calibrated': bool,
        }
    """
    # Filter resolved predictions
    resolved = [p for p in predictions if p.get('actual_outcome') is not None]
    
    if len(resolved) < 10:
        return {
            'calibration_curve': [],
            'brier_score': None,
            'is_well_calibrated': False,
            'note': 'Insufficient data for calibration (need 10+ resolved predictions)'
        }
    
    # Bin predictions by probability
    bins = [[] for _ in range(bin_count)]
    for pred in resolved:
        prob = pred['adjusted_probability']
        bin_idx = min(int(prob * bin_count), bin_count - 1)
        bins[bin_idx].append(pred)
    
    # Calculate actual frequency per bin
    calibration_curve = []
    for i, bin_preds in enumerate(bins):
        if bin_preds:
            predicted_prob = (i + 0.5) / bin_count
            actual_freq = sum(1 for p in bin_preds if p['actual_outcome'] == 'YES') / len(bin_preds)
            calibration_curve.append((predicted_prob, actual_freq))
    
    # Brier score
    brier = sum(
        (p['adjusted_probability'] - (1 if p['actual_outcome'] == 'YES' else 0)) ** 2
        for p in resolved
    ) / len(resolved)
    
    return {
        'calibration_curve': calibration_curve,
        'brier_score': round(brier, 4),
        'is_well_calibrated': brier < 0.25,
        'sample_size': len(resolved),
    }
```

### 5. Complete Prediction Pipeline

```python
def generate_prediction(
    seed_material: str,
    prediction_question: str,
    market_type: str = 'crypto',
    ensemble_size: int = 3,
    agent_count: int = 200,
    simulation_rounds: int = 50,
) -> Dict:
    """
    Complete prediction pipeline: seed -> graph -> agents -> simulation -> prediction.
    """
    print("=" * 60)
    print(f"MiroFish Prediction Engine")
    print(f"Question: {prediction_question}")
    print("=" * 60)
    
    # Step 1: Build knowledge graph
    print("\n[1/5] Building knowledge graph...")
    from knowledge_graph import build_knowledge_graph_pipeline
    kg_result = build_knowledge_graph_pipeline(
        project_name=f"pred_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        seed_material=seed_material,
    )
    print(f"Graph: {kg_result['stats']['node_count']} nodes, {kg_result['stats']['edge_count']} edges")
    
    # Step 2: Generate agents
    print(f"\n[2/5] Generating {agent_count} agent personas...")
    from sentiment_simulation import generate_agent_personas
    agents = generate_agent_personas(kg_result['export_data'], total_agents=agent_count)
    print(f"Generated {len(agents)} agents")
    
    # Step 3: Run ensemble simulations
    print(f"\n[3/5] Running {ensemble_size} ensemble simulations...")
    from sentiment_simulation import OASISSimulation, configure_simulation
    
    simulation_runs = []
    for i in range(ensemble_size):
        print(f"  Run {i+1}/{ensemble_size}...")
        sim_config = configure_simulation(agents, prediction_question, random_seed=42+i)
        sim = OASISSimulation(sim_config)
        results = sim.run()
        simulation_runs.append(results)
    
    # Step 4: Extract consensus
    print(f"\n[4/5] Extracting ensemble consensus...")
    consensus = extract_ensemble_consensus(simulation_runs, prediction_question)
    print(f"Raw probability: {consensus['ensemble_mean']:.2%} (±{consensus['std_dev']:.2%})")
    
    # Step 5: Apply uncertainty discount
    print(f"\n[5/5] Applying uncertainty discount...")
    calibrated = apply_uncertainty_discount(
        raw_prob=consensus['ensemble_mean'],
        std_dev=consensus['std_dev'],
        info_quality=0.7,
        market_type=market_type,
    )
    print(f"Calibrated probability: {calibrated['adjusted_probability']:.2%}")
    print(f"Uncertainty: {calibrated['uncertainty']:.2%}")
    
    # Compile final prediction
    prediction = {
        'prediction_id': f"PRED-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
        'question': prediction_question,
        'timestamp': datetime.now().isoformat(),
        'raw_probability': consensus['ensemble_mean'],
        'adjusted_probability': calibrated['adjusted_probability'],
        'uncertainty': calibrated['uncertainty'],
        'confidence': consensus['confidence_label'],
        'std_dev': consensus['std_dev'],
        'range': (consensus['min_prob'], consensus['max_prob']),
        'catalysts': extract_catalysts(simulation_runs[0]),
        'info_quality': calibrated['info_quality'],
        'market_type': market_type,
    }
    
    print("\n" + "=" * 60)
    print(f"FINAL PREDICTION: {prediction['adjusted_probability']:.2%} ({prediction['confidence']} confidence)")
    print("=" * 60)
    
    return prediction
```

## Pitfalls

- **Overconfidence**: Raw simulation probabilities are often overconfident — always apply uncertainty discount
- **Small ensembles**: Fewer than 3 runs gives unreliable estimates
- **Ignoring market type**: Crypto markets need different uncertainty adjustments than sports
- **No calibration**: Without tracking outcomes, predictions drift from reality
- **Cherry-picking runs**: Report all ensemble results, not just favorable ones

## Verification

- Ensemble standard deviation is calculated and reported
- Uncertainty discount is applied and documented
- All 3 scenarios (baseline, bull, bear) produce different probabilities
- Prediction is registered for future calibration
- Confidence label reflects true uncertainty (not wishful thinking)
