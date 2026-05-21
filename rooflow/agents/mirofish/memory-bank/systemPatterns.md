# System Patterns — MiroFish Prediction Engine

## Simulation Templates

### Pattern: Standard Crypto Prediction
```
1. Receive data request from Crypto Monitor
2. Gather seed material (market data + news)
3. Build knowledge graph with crypto ontology
4. Generate 200 diverse agents (6 archetypes)
5. Run 3 ensemble simulations (50 rounds each)
6. Extract consensus probability
7. Apply uncertainty discount (crypto: 1.15x)
8. Create prediction packet for Polymarket Analyzer
9. Register prediction for calibration tracking
```

### Pattern: Fast Sentiment Scan
```
1. Receive request from Crypto Monitor
2. Use lightweight seed (headlines only)
3. Generate 100 agents (simplified archetypes)
4. Run single simulation (30 rounds)
5. Extract sentiment distribution
6. Deliver sentiment brief to Crypto Monitor
```

### Pattern: Polymarket Deep Analysis
```
1. Receive market question from Polymarket Analyzer
2. Gather comprehensive seed (order book + news + rules)
3. Build detailed knowledge graph
4. Generate 500 agents
5. Run 5 ensemble simulations (60 rounds each)
6. Run bull/bear shock scenarios
7. Apply uncertainty discount
8. Create full analysis report + prediction packet
```

## Calibration Patterns

### Pattern: Weekly Calibration Review
```python
# 1. Read predictionRegistry.md
# 2. Filter resolved predictions
# 3. Calculate Brier score
# 4. Generate calibration curve
# 5. Adjust multipliers if needed
# 6. Document in decisionLog.md
```

## Knowledge Graph Patterns

### Pattern: Crypto Market Ontology
Entity types: Cryptocurrency, Exchange, Regulator, Institution, Person, Event, Technology, Market, Media, Metric
Relation types: INFLUENCES, REGULATES, TRADES_ON, SUPPORTS, OPPOSES, CREATED, REPORTS_ON, CORRELATES_WITH

### Pattern: Prediction Market Ontology
Entity types: Market, Outcome, Trader, Event, Source, Rule, Asset, Platform, Analyst, Trend
Relation types: RESOLVES_TO, TRADES_ON, INFLUENCES, DEPENDS_ON, CONTRADICTS, SUPPORTS, CORRELATES_WITH

## Prediction Packet Template

### Standard Format for Polymarket Analyzer
```json
{
  "packet_id": "PKT-YYYYMMDD-HHMMSS",
  "prediction": {
    "question": "...",
    "probability_yes": 0.65,
    "confidence": "MEDIUM",
    "uncertainty": 0.08
  },
  "scenarios": {
    "baseline": {"probability": 0.65},
    "bull_shock": {"probability": 0.82, "delta": +0.17},
    "bear_shock": {"probability": 0.48, "delta": -0.17}
  },
  "catalysts": ["...", "...", "..."],
  "methodology": {
    "agent_count": 200,
    "ensemble_runs": 3,
    "simulation_rounds": 50
  }
}
```

## Collaboration Patterns

### Pattern: Receiving Data from Crypto Monitor
1. Check shared-memory-bank/handoffs.md
2. Validate incoming data (freshness, completeness)
3. Acknowledge receipt
4. Integrate into seed material

### Pattern: Delivering to Polymarket Analyzer
1. Create prediction packet
2. Write to shared-memory-bank/handoffs.md
3. Include full methodology and risk factors
4. Update executionLog.md

### Pattern: Sentiment Brief to Crypto Monitor
1. Extract sentiment from simulation
2. Identify divergence signals
3. Create lightweight brief
4. Deliver via shared Memory Bank
