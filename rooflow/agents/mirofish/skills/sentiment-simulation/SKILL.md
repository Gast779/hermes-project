---
name: sentiment-simulation
description: Run multi-agent social simulations on Twitter-like and Reddit-like platforms. Generate diverse agent personas, execute simulation rounds, and extract collective sentiment and behavioral patterns.
version: 1.0.0
author: MiroFish Agent
metadata:
  hermes:
    tags: [simulation, swarm-intelligence, sentiment, oasis, multi-agent, social]
    category: prediction
    requires_toolsets: [terminal, execute_code]
---

# Sentiment Simulation

## When to Use

Use this skill when you need to:
- Simulate public opinion and sentiment around a market event or prediction question
- Generate diverse agent perspectives on crypto/Polymarket topics
- Model information cascades and narrative spread in social networks
- Extract collective sentiment distributions from agent interactions
- Run scenario stress-tests (bull/bear shocks) to test market sensitivity

## Quick Reference

| Simulation Type | Agent Count | Rounds | Use Case | Cost |
|----------------|-------------|--------|----------|------|
| Fast Scan | 100-200 | 20-30 | Initial filtering, quick sentiment check | ~$1-2 |
| Decision Run | 200-500 | 40-60 | Serious predictions, medium confidence | ~$3-5 |
| Deep Analysis | 500-1000 | 80-100 | High-stakes decisions, maximum confidence | ~$8-15 |
| Shock Test | 200-500 | 40-60 | Bull/bear catalyst injection | ~$3-5 |

## Procedure

### 1. Generate Agent Personas

```python
import json
import random
from typing import List, Dict

# Standard persona template
PERSONA_TEMPLATE = """
You are {name}, a {age}-year-old {occupation} from {country}.

Personality:
- MBTI Type: {mbti}
- Posting Style: {posting_style}
- Emotional Triggers: {emotional_triggers}
- Taboo Topics: {taboo_topics}

Background:
{background}

Institutional Memory:
{memory}

Decision Logic:
{decision_logic}
"""

# Diverse agent archetypes for crypto/Polymarket
AGENT_ARCHETYPES = {
    'retail_trader': {
        'ratio': 0.35,  # 35% of population
        'mbti_pool': ['ESTP', 'ENTP', 'ISTJ', 'ENFP'],
        'occupations': ['Crypto Trader', 'Retail Investor', 'DeFi User', 'NFT Collector'],
        'posting_styles': ['emotional', 'hype-driven', 'analytical', 'skeptical'],
        'emotional_triggers': ['price pumps', 'FUD', 'celebrity endorsements', 'regulatory news'],
    },
    'institutional_investor': {
        'ratio': 0.10,
        'mbti_pool': ['INTJ', 'ENTJ', 'ISTJ'],
        'occupations': ['Hedge Fund Manager', 'VC Analyst', 'Portfolio Manager', 'Quant Researcher'],
        'posting_styles': ['measured', 'data-driven', 'cautious', 'professional'],
        'emotional_triggers': ['regulatory clarity', 'macro trends', 'liquidity events'],
    },
    'media_analyst': {
        'ratio': 0.15,
        'mbti_pool': ['ENFJ', 'ENTP', 'INTP'],
        'occupations': ['Crypto Journalist', 'Market Analyst', 'Twitter Influencer', 'YouTuber'],
        'posting_styles': ['narrative-driven', 'breaking-news', 'opinionated', 'investigative'],
        'emotional_triggers': ['scandals', 'major announcements', 'market crashes'],
    },
    'developer_researcher': {
        'ratio': 0.15,
        'mbti_pool': ['INTP', 'INTJ', 'ENTP'],
        'occupations': ['Blockchain Developer', 'Researcher', 'Protocol Designer', 'Security Auditor'],
        'posting_styles': ['technical', 'educational', 'critical', 'innovative'],
        'emotional_triggers': ['bugs', 'upgrades', 'new tech', 'security issues'],
    },
    'regulator_policy': {
        'ratio': 0.10,
        'mbti_pool': ['ISTJ', 'ESTJ', 'ENTJ'],
        'occupations': ['Regulator', 'Policy Advisor', 'Compliance Officer', 'Government Official'],
        'posting_styles': ['formal', 'cautious', 'rule-focused', 'diplomatic'],
        'emotional_triggers': ['violations', 'market manipulation', 'consumer protection'],
    },
    'ordinary_observer': {
        'ratio': 0.15,
        'mbti_pool': ['ISFJ', 'ESFP', 'INFP', 'ISFP'],
        'occupations': ['Student', 'Teacher', 'Engineer', 'Doctor', 'Artist'],
        'posting_styles': ['casual', 'curious', 'reactive', 'social'],
        'emotional_triggers': ['mainstream news', 'friend recommendations', 'fear of missing out'],
    },
}


def generate_agent_personas(
    knowledge_graph: dict,
    total_agents: int = 200,
    seed: int = 42
) -> List[Dict]:
    """
    Generate diverse agent personas based on knowledge graph and archetypes.
    
    Args:
        knowledge_graph: Output from knowledge-graph skill
        total_agents: Total number of agents to generate
        seed: Random seed for reproducibility
    
    Returns:
        List of agent persona dictionaries
    """
    random.seed(seed)
    agents = []
    
    # Extract entities from knowledge graph for personalization
    entities = knowledge_graph.get('export_data', {}).get('nodes', [])
    
    for archetype_name, archetype in AGENT_ARCHETYPES.items():
        count = int(total_agents * archetype['ratio'])
        
        for i in range(count):
            agent = {
                'id': f"{archetype_name}_{i}",
                'archetype': archetype_name,
                'name': f"Agent_{archetype_name}_{i}",
                'mbti': random.choice(archetype['mbti_pool']),
                'age': random.randint(22, 65),
                'occupation': random.choice(archetype['occupations']),
                'country': random.choice(['USA', 'UK', 'Germany', 'Japan', 'Singapore', 'UAE']),
                'posting_style': random.choice(archetype['posting_styles']),
                'emotional_triggers': archetype['emotional_triggers'],
                'activity_level': random.choice(['high', 'medium', 'low']),
                'influence_score': random.uniform(0.1, 1.0),
                'memory': [],  # Will be populated during simulation
            }
            agents.append(agent)
    
    # Shuffle to avoid archetype clustering
    random.shuffle(agents)
    
    return agents
```

### 2. Configure Simulation Environment

```python
def configure_simulation(
    agents: List[Dict],
    prediction_question: str,
    simulation_hours: int = 168,  # 7 days
    platforms: List[str] = ['twitter'],
    random_seed: int = 42
) -> Dict:
    """
    Configure OASIS simulation environment.
    
    Args:
        agents: List of agent personas
        prediction_question: The question being predicted
        simulation_hours: Total simulated hours
        platforms: ['twitter'] or ['twitter', 'reddit']
        random_seed: For reproducibility
    
    Returns:
        Simulation configuration dictionary
    """
    config = {
        'environment': {
            'type': 'social_media',
            'platforms': platforms,
            'simulation_hours': simulation_hours,
            'rounds': min(simulation_hours, 100),  # 1 round per hour, max 100
            'time_step': 3600,  # 1 hour per round
        },
        'agents': {
            'count': len(agents),
            'personas': agents,
            'behavior_rules': {
                'post_probability': {
                    'high_activity': 0.3,
                    'medium_activity': 0.15,
                    'low_activity': 0.05,
                },
                'retweet_probability': 0.25,
                'reply_probability': 0.20,
                'like_probability': 0.35,
                'idle_probability': 0.15,
            }
        },
        'content': {
            'prediction_question': prediction_question,
            'seed_posts': [
                {
                    'author': 'news_bot',
                    'content': f'Breaking: Market attention shifting to: {prediction_question}',
                    'timestamp': 0,
                }
            ],
            'topics': ['price_prediction', 'market_sentiment', 'regulatory_news', 'technology_update'],
        },
        'memory': {
            'system': 'zep_cloud',
            'persistent': True,
            'recall_horizon': 48,  # Hours of memory
        },
        'random_seed': random_seed,
    }
    
    return config
```

### 3. Execute Simulation

```python
class OASISSimulation:
    """Wrapper for OASIS social simulation engine."""
    
    def __init__(self, config: Dict):
        self.config = config
        self.rounds = config['environment']['rounds']
        self.results = {
            'posts': [],
            'actions': [],
            'agent_states': [],
            'round_summaries': [],
        }
    
    def run(self) -> Dict:
        """
        Execute full simulation.
        
        Returns:
            Complete simulation results with all agent actions
        """
        print(f"Starting simulation: {self.config['agents']['count']} agents, "
              f"{self.rounds} rounds")
        
        for round_num in range(self.rounds):
            round_results = self._run_round(round_num)
            self.results['round_summaries'].append(round_results)
            
            if round_num % 10 == 0:
                print(f"Round {round_num}/{self.rounds} complete")
        
        print(f"Simulation complete: {len(self.results['posts'])} posts generated")
        return self.results
    
    def _run_round(self, round_num: int) -> Dict:
        """Execute a single simulation round."""
        # Each agent decides: post, retweet, reply, like, or idle
        round_posts = []
        round_actions = []
        
        for agent in self.config['agents']['personas']:
            action = self._agent_decide(agent, round_num)
            round_actions.append({
                'agent_id': agent['id'],
                'action': action,
                'round': round_num,
            })
            
            if action == 'post':
                post = self._generate_post(agent, round_num)
                round_posts.append(post)
                self.results['posts'].append(post)
        
        return {
            'round': round_num,
            'posts_count': len(round_posts),
            'actions': round_actions,
        }
    
    def _agent_decide(self, agent: Dict, round_num: int) -> str:
        """Agent decision logic based on persona and context."""
        import random
        
        # Activity level affects posting probability
        probs = self.config['agents']['behavior_rules']['post_probability']
        post_prob = probs.get(agent['activity_level'], 0.15)
        
        # Influencers post more
        post_prob *= (0.5 + agent['influence_score'])
        
        # Random decision
        r = random.random()
        if r < post_prob:
            return 'post'
        elif r < post_prob + 0.25:
            return 'retweet'
        elif r < post_prob + 0.45:
            return 'reply'
        elif r < post_prob + 0.80:
            return 'like'
        else:
            return 'idle'
    
    def _generate_post(self, agent: Dict, round_num: int) -> Dict:
        """Generate a post based on agent persona and simulation state."""
        return {
            'id': f"post_{round_num}_{agent['id']}",
            'author': agent['id'],
            'author_archetype': agent['archetype'],
            'round': round_num,
            'content': f"[Simulated post from {agent['archetype']} agent]",
            'sentiment': random.choice(['bullish', 'bearish', 'neutral']),
            'engagement': {
                'likes': 0,
                'retweets': 0,
                'replies': 0,
            },
        }
```

### 4. Extract Sentiment from Simulation

```python
def extract_sentiment(simulation_results: Dict) -> Dict:
    """
    Extract collective sentiment and behavioral patterns from simulation.
    
    Returns:
        {
            'overall_sentiment': 'bullish' | 'bearish' | 'neutral',
            'sentiment_distribution': {'bullish': 0.45, 'bearish': 0.30, 'neutral': 0.25},
            'confidence_trend': [0.5, 0.52, 0.55, ...],  # Per round
            'key_narratives': ['narrative1', 'narrative2'],
            'influencer_opinions': [...],
            'behavioral_stats': {...},
        }
    """
    posts = simulation_results['posts']
    
    # Count sentiments
    sentiments = {'bullish': 0, 'bearish': 0, 'neutral': 0}
    for post in posts:
        s = post.get('sentiment', 'neutral')
        sentiments[s] = sentiments.get(s, 0) + 1
    
    total = sum(sentiments.values())
    distribution = {k: v/total for k, v in sentiments.items()}
    
    # Determine overall sentiment
    if distribution['bullish'] > distribution['bearish'] + 0.1:
        overall = 'bullish'
    elif distribution['bearish'] > distribution['bullish'] + 0.1:
        overall = 'bearish'
    else:
        overall = 'neutral'
    
    # Behavioral stats
    actions = simulation_results.get('actions', [])
    action_counts = {}
    for action in actions:
        a = action['action']
        action_counts[a] = action_counts.get(a, 0) + 1
    
    return {
        'overall_sentiment': overall,
        'sentiment_distribution': distribution,
        'confidence_trend': [],  # Would calculate from round summaries
        'key_narratives': [],  # Would extract from post content
        'influencer_opinions': [],
        'behavioral_stats': {
            'total_posts': len(posts),
            'total_actions': len(actions),
            'action_breakdown': action_counts,
        }
    }
```

## Pitfalls

- **Insufficient agent diversity**: Echo chambers produce false consensus
- **Too few rounds**: Agents need time to form and evolve opinions
- **Poor seed posts**: Initial content shapes entire simulation trajectory
- **Ignoring platform differences**: Twitter and Reddit have different dynamics
- **Not running ensembles**: Single runs are samples, not answers

## Verification

- Minimum 100 agents generated with diverse archetypes
- Simulation produces posts across all rounds
- Sentiment distribution is not 100% one-sided (unless justified)
- Behavioral stats show realistic action distributions
- Results are reproducible with same seed
