---
name: memory-bank-workflow
description: RooFlow Memory Bank management for MiroFish — initialize, read, update, and sync Memory Bank files. Coordinate with Crypto Monitor and Polymarket Analyzer via shared Memory Bank.
version: 1.0.0
author: MiroFish Agent
metadata:
  hermes:
    tags: [memory-bank, rooflow, context, persistence, multi-agent]
    category: workflow
    requires_toolsets: [files]
---

# RooFlow Memory Bank Workflow (MiroFish)

## When to Use

Use this skill when you need to:
- Initialize Memory Bank for prediction projects
- Read data requests from Crypto Monitor or Polymarket Analyzer
- Update prediction registry and calibration tracking
- Sync with shared Memory Bank for multi-agent handoffs
- Recover context after interruption (UMB command)

## Memory Bank Structure

```
memory-bank/
├── activeContext.md      # Current session state, active simulations
├── productContext.md     # Prediction inventory, ontology library
├── progress.md           # Simulation tracking, calibration history
├── decisionLog.md        # Simulation design decisions, methodology choices
└── systemPatterns.md     # Reusable simulation templates, calibration curves

shared-memory-bank/       # Shared with partner agents
├── projectBrief.md       # Overall project goals
├── handoffs.md           # Active handoffs (all agents)
├── dataContracts.md      # Data schemas and prediction packet format
├── executionLog.md       # Simulation execution history
└── predictionRegistry.md # All predictions with outcomes for calibration
```

## Quick Reference

| Action | File to Update |
|--------|---------------|
| Receive data request | Read `../shared-memory-bank/handoffs.md` |
| Start simulation | Update `activeContext.md` + `progress.md` |
| Complete prediction | Update `progress.md` + write to `predictionRegistry.md` |
| Deliver to Polymarket Analyzer | Write prediction packet to handoffs |
| Update calibration | Read/write `predictionRegistry.md` |
| Discover pattern | Update `systemPatterns.md` |

## Procedure

### 1. Initialize Memory Bank
```python
import os
from datetime import datetime

def initialize_memory_bank(base_path='memory-bank'):
    """Create Memory Bank directory and all core files for MiroFish."""
    os.makedirs(base_path, exist_ok=True)
    
    files = {
        'activeContext.md': '''# Active Context

## Current Session
[Prediction task in progress]

## Active Simulations
- [ ] [Simulation name] — [Status]

## Pending Data Requests
- From Crypto Monitor: [request details]
- From Polymarket Analyzer: [request details]

## Blockers
- None

## Alerts
- None
''',
        'productContext.md': '''# Product Context

## Prediction Inventory
| Prediction | Status | Agents | Runs | Date |
|------------|--------|--------|------|------|
| [Name] | [Status] | [Count] | [Runs] | [Date] |

## Ontology Library
| Ontology | Entity Types | Use Case | Reusable |
|----------|-------------|----------|----------|
| crypto_standard | 10 | Crypto markets | Yes |
| [Custom] | [N] | [Use case] | [Yes/No] |

## Knowledge Graph Versions
| Graph ID | Entities | Relations | Status |
|----------|----------|-----------|--------|
| [UUID] | [Count] | [Count] | [Active/Archived] |

## Calibration Status
- Predictions tracked: [N]
- Resolved predictions: [N]
- Brier score: [Score]
- Well calibrated: [Yes/No]
''',
        'progress.md': '''# Progress Tracking

## Completed Simulations
- [YYYY-MM-DD]: [Simulation completed] — [Key finding]

## Current Predictions
- [ ] [Prediction in progress]

## Calibration Updates
- [YYYY-MM-DD]: [N] new predictions resolved, Brier score updated

## Known Issues
- [Issue]: [Status, workaround]
''',
        'decisionLog.md': '''# Decision Log

## Simulation Design Decisions

### [YYYY-MM-DD] Agent Population Size
- **Context**: Need to balance cost vs accuracy
- **Decision**: Use 200 agents for standard, 500+ for high-stakes
- **Rationale**: 200 agents sufficient for directional accuracy; 500+ for precise probability estimates
- **Alternatives**: 100 (too few), 1000 (too expensive)
- **Impact**: Cost-effective predictions with acceptable accuracy

### [YYYY-MM-DD] Uncertainty Discount Formula
- **Context**: Raw simulation probabilities are overconfident
- **Decision**: Apply shrinkage toward 50% based on std dev, info quality, market type
- **Rationale**: Empirical testing shows raw probs need 5-15% adjustment
- **Impact**: Better calibrated predictions
''',
        'systemPatterns.md': '''# System Patterns

## Simulation Templates

### Pattern: Standard Crypto Prediction
1. Gather market data from Crypto Monitor
2. Build knowledge graph with crypto ontology
3. Generate 200 diverse agents
4. Run 3 ensemble simulations (50 rounds each)
5. Apply uncertainty discount (crypto multiplier: 1.15)
6. Deliver prediction packet to Polymarket Analyzer

### Pattern: Fast Sentiment Scan
1. Use lightweight seed material (news headlines)
2. Generate 100 agents
3. Run single simulation (30 rounds)
4. Extract sentiment distribution
5. Deliver sentiment brief to Crypto Monitor

## Calibration Patterns

### Pattern: Weekly Calibration Review
1. Read predictionRegistry.md for resolved predictions
2. Calculate Brier score and calibration curve
3. Adjust uncertainty multipliers if needed
4. Document findings in decisionLog.md

## Knowledge Graph Patterns

### Pattern: Crypto Market Ontology
Standard entity types: Cryptocurrency, Exchange, Regulator, Institution, Person, Event, Technology, Market, Media, Metric

### Pattern: Geopolitical Ontology
Standard entity types: Country, Military, Diplomat, Media, Organization, Economic Entity, Infrastructure, Individual
'''
    }
    
    for filename, content in files.items():
        filepath = os.path.join(base_path, filename)
        if not os.path.exists(filepath):
            with open(filepath, 'w') as f:
                f.write(content)
            print(f"Created: {filepath}")
        else:
            print(f"Exists: {filepath}")
    
    return base_path
```

### 2. Read Partner Agent Requests
```python
def read_partner_requests(shared_path='../shared-memory-bank'):
    """Read data/prediction requests from Crypto Monitor and Polymarket Analyzer."""
    handoffs_file = os.path.join(shared_path, 'handoffs.md')
    
    if not os.path.exists(handoffs_file):
        return []
    
    with open(handoffs_file, 'r') as f:
        content = f.read()
    
    # Parse handoff entries targeting MiroFish
    requests = []
    # Look for entries where 'to_agent' is 'mirofish'
    
    return requests


def acknowledge_request(request_id, shared_path='../shared-memory-bank'):
    """Acknowledge a data/prediction request."""
    handoffs_file = os.path.join(shared_path, 'handoffs.md')
    
    with open(handoffs_file, 'r') as f:
        content = f.read()
    
    # Update status to 'in_progress'
    content = content.replace(
        f'ID: {request_id}\nStatus: pending',
        f'ID: {request_id}\nStatus: in_progress'
    )
    
    with open(handoffs_file, 'w') as f:
        f.write(content)
```

### 3. Register Prediction
```python
def register_prediction(prediction, shared_path='../shared-memory-bank'):
    """Register prediction in shared registry for calibration tracking."""
    registry_file = os.path.join(shared_path, 'predictionRegistry.md')
    
    entry = f"""
### Prediction: {prediction['prediction_id']}
- **Timestamp**: {prediction['timestamp']}
- **Question**: {prediction['question']}
- **Adjusted Probability**: {prediction['adjusted_probability']:.2%}
- **Confidence**: {prediction['confidence']}
- **Source Agents**: MiroFish ({prediction.get('agent_count', 200)} agents)
- **Resolution Date**: [To be filled]
- **Actual Outcome**: [Pending resolution]

"""
    
    with open(registry_file, 'a') as f:
        f.write(entry)
```

### 4. Full UMB Sync
```python
def full_umb_sync(local_path='memory-bank', shared_path='../shared-memory-bank'):
    """Full Update Memory Bank sync for MiroFish."""
    print("=== MiroFish UMB Sync ===")
    
    # Read all local Memory Bank files
    local_files = ['activeContext.md', 'productContext.md', 'progress.md', 
                   'decisionLog.md', 'systemPatterns.md']
    
    local_context = {}
    for filename in local_files:
        filepath = os.path.join(local_path, filename)
        if os.path.exists(filepath):
            with open(filepath, 'r') as f:
                local_context[filename] = f.read()
    
    # Read shared Memory Bank
    shared_files = ['handoffs.md', 'executionLog.md', 'predictionRegistry.md']
    
    shared_context = {}
    for filename in shared_files:
        filepath = os.path.join(shared_path, filename)
        if os.path.exists(filepath):
            with open(filepath, 'r') as f:
                shared_context[filename] = f.read()
    
    # Summarize
    summary = f"""
## UMB Sync — {datetime.now().isoformat()}

### MiroFish Status
- Active simulations: [from activeContext.md]
- Pending partner requests: [from handoffs.md]
- Predictions registered: [from predictionRegistry.md]
- Calibration status: [from progress.md]

### Next Actions
- [Priority action from context]
"""
    
    with open(os.path.join(local_path, 'activeContext.md'), 'a') as f:
        f.write(summary)
    
    print("=== UMB Sync Complete ===")
    return summary
```

## Pitfalls

- **Missing partner requests**: Always check shared handoffs at session start
- **Not registering predictions**: Without registration, calibration is impossible
- **Stale calibration data**: Review calibration weekly
- **Out of sync**: Sync both local and shared Memory Bank after each prediction

## Verification

- All Memory Bank files exist and are readable
- Shared predictionRegistry.md is updated after each prediction
- Partner requests are acknowledged promptly
- UMB sync completes without errors
