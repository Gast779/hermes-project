"""
Resolution Risk Scoring для Polymarket markets.

Polymarket використовує UMA optimistic oracle.
Резолюції можуть бути disputed, ambiguous, delayed.

Цей модуль читає question + description + resolution_source і дає
risk score [0-1]. High risk = НЕ торгувати або low confidence.
"""
import re
from dataclasses import dataclass
from typing import List


@dataclass
class ResolutionRiskScore:
    overall_risk: float          # [0=safe, 1=very risky]
    ambiguity_score: float
    source_reliability: float
    timing_risk: float
    historical_disputes: int     # відомі disputed markets за подібним wording
    red_flags: List[str]
    safe_to_trade: bool


# Ambiguous wording patterns
AMBIGUOUS_KEYWORDS = {
    # high risk — historically disputed
    "leave office": 0.8,         # death? resign? lose election? (Khamenei case)
    "stop": 0.6,                 # what counts as "stopping"?
    "agree to": 0.7,             # formal vs verbal agreement
    "officially": 0.5,
    "publicly": 0.4,
    "before end of": 0.3,        # ambiguous time zone
    "win": 0.4,                  # championship? game? round?
    "approve": 0.5,
    "sign": 0.4,
    "ban": 0.5,
    "endorse": 0.6,
    # medium risk
    "by": 0.3,
    "during": 0.4,
    "say": 0.5,                  # tweet? interview? statement?
    "criticize": 0.6,
    "meet with": 0.5,
}

# Trusted resolution sources
TRUSTED_SOURCES = {
    "official government": 0.95,
    "sec.gov": 0.95,
    "federal register": 0.95,
    "reuters": 0.90,
    "bloomberg": 0.90,
    "associated press": 0.90,
    "official statement": 0.80,
    "press release": 0.75,
    "twitter": 0.50,             # subjective
    "x.com": 0.50,
    "social media": 0.40,
    "tweet": 0.45,
}


def score_resolution_risk(
    market: dict,
    known_disputes_count: int = 0,
) -> ResolutionRiskScore:
    """
    Scoring algorithm.

    Args:
        market: dict with question, description, resolution_source
        known_disputes_count: how many similar markets had disputes

    Returns:
        ResolutionRiskScore
    """
    question = market.get("question", "").lower()
    description = market.get("description", "").lower()
    source = market.get("resolution_source", "").lower()

    red_flags = []
    ambiguity_score = 0

    # 1. Check ambiguous keywords
    for keyword, weight in AMBIGUOUS_KEYWORDS.items():
        if keyword in question or keyword in description:
            ambiguity_score = max(ambiguity_score, weight)
            red_flags.append(f"Ambiguous: '{keyword}'")

    # 2. Numeric specificity = good
    has_specific_number = bool(re.search(r'\$[\d,]+|\d+%|\d+ (votes|seats|points)', question))
    if not has_specific_number and "be above" not in question and "exceed" not in question:
        ambiguity_score = max(ambiguity_score, 0.3)
        red_flags.append("No specific numeric criteria")

    # 3. Time zone specification
    has_timezone = any(tz in description for tz in ["UTC", "EST", "PT", "ET", "GMT"])
    has_specific_date = bool(re.search(r'\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*\s+\d{1,2}', question.lower()))
    if has_specific_date and not has_timezone:
        red_flags.append("Date without timezone — UMA timestamp risk")
        ambiguity_score = max(ambiguity_score, 0.4)

    # 4. Source reliability
    source_reliability = 0.5  # default unknown
    for src, score in TRUSTED_SOURCES.items():
        if src in source or src in description:
            source_reliability = max(source_reliability, score)
            break

    # 5. Timing risk — events that may extend past resolution
    timing_risk = 0
    if "pending" in description or "challenge" in description:
        timing_risk = 0.5
        red_flags.append("Pending/challenge wording")
    if "binding" not in description and "official" not in description:
        timing_risk = max(timing_risk, 0.3)

    # 6. Historical disputes
    historical_penalty = min(0.5, known_disputes_count * 0.1)

    # Combined risk
    overall_risk = min(1.0, (
        ambiguity_score * 0.4 +
        (1 - source_reliability) * 0.3 +
        timing_risk * 0.2 +
        historical_penalty * 0.1
    ))

    safe_to_trade = overall_risk < 0.35

    return ResolutionRiskScore(
        overall_risk=overall_risk,
        ambiguity_score=ambiguity_score,
        source_reliability=source_reliability,
        timing_risk=timing_risk,
        historical_disputes=known_disputes_count,
        red_flags=red_flags,
        safe_to_trade=safe_to_trade,
    )


def filter_safe_markets(markets: list[dict], min_safety: float = 0.6) -> list[dict]:
    """Повертає тільки markets з resolution risk < (1 - min_safety)."""
    safe = []
    for m in markets:
        score = score_resolution_risk(m)
        if score.safe_to_trade:
            m["_resolution_risk_score"] = score
            safe.append(m)
    return safe
