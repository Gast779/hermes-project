# Decision Log — MiroFish Prediction Engine

## Simulation Design Decisions

### [YYYY-MM-DD] Agent Population Architecture
- **Context**: Need to define agent archetypes for crypto/polymarket simulations
- **Decision**: 6 archetypes (retail 35%, institutional 10%, media 15%, developer 15%, regulator 10%, observer 15%)
- **Rationale**: 
  - Retail traders dominate social media discourse
  - Institutional voices carry disproportionate weight
  - Media shapes narratives
  - Developers provide technical perspective
  - Regulators influence long-term sentiment
  - Observers represent general public
- **Alternatives**: Fewer archetypes (loses nuance), more archetypes (overly complex)
- **Impact**: Diverse, realistic agent population

### [YYYY-MM-DD] Uncertainty Discount Formula Selection
- **Context**: Raw simulation probabilities tend to be overconfident
- **Decision**: Apply shrinkage toward 50% using formula: adjusted = raw + (0.50 - raw) × uncertainty
  - uncertainty = std_dev × 2.0 × (2.0 - info_quality) × market_multiplier
  - crypto multiplier: 1.15
  - geopolitical multiplier: 1.20
- **Rationale**: Empirical research shows LLM-based predictions need 5-20% uncertainty adjustment
- **Impact**: Better calibrated, less overconfident predictions

### [YYYY-MM-DD] Ensemble Size Standard
- **Context**: Single simulation runs produce variable results
- **Decision**: Minimum 3 independent runs for all predictions; 5+ for high-stakes decisions
- **Rationale**: 
  - 3 runs sufficient to estimate variance
  - Diminishing returns after 5 runs
  - Cost increases linearly with run count
- **Impact**: Reliable variance estimation without excessive cost

### [YYYY-MM-DD] RooFlow Integration for Multi-Agent System
- **Context**: Need to integrate with existing Hermes system (Crypto Monitor, Polymarket Analyzer, English Bot)
- **Decision**: Implement shared Memory Bank + prediction packet protocol
- **Rationale**: 
  - Shared Memory Bank: All agents read/write context
  - Prediction packets: Structured format for Polymarket Analyzer
  - Sentiment briefs: Lightweight format for Crypto Monitor
- **Impact**: Seamless collaboration with partner agents
