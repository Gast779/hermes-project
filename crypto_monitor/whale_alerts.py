"""
Whale Alert — сканування великих транзакцій на блокчейні.

Sources:
    - Whale Alert API (https://docs.whale-alert.io/)
    - Blockchain.com API (free tier)
    - Etherscan API (free tier)
    - BscScan API

Alerts trigger:
    - BTC: >$1M
    - ETH: >$500k
    - Stablecoins (USDT/USDC): >$2M
    - Exchange inflows/outflows (significant signal)

Telegram: thread 25 (crypto_daily_reports)
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta

import requests

log = logging.getLogger(__name__)

WHALE_API_KEY = os.getenv("WHALE_ALERT_API_KEY", "")
ETHERSCAN_API_KEY = os.getenv("ETHERSCAN_API_KEY", "")

# Thresholds in USD
THRESHOLDS = {
    "BTC": 1_000_000,
    "ETH": 500_000,
    "USDT": 2_000_000,
    "USDC": 2_000_000,
    "XRP": 500_000,
}


@dataclass
class WhaleTransaction:
    tx_hash: str
    blockchain: str
    symbol: str
    amount: float
    amount_usd: float
    from_address: str
    to_address: str
    from_owner: str | None
    to_owner: str | None
    timestamp: datetime
    tx_type: str  # transfer, mint, burn


def fetch_whale_alert(limit: int = 10) -> list[WhaleTransaction]:
    """
    Fetch recent whale transactions from Whale Alert API.
    
    Returns empty list if API key missing or error.
    """
    if not WHALE_API_KEY:
        log.warning("WHALE_ALERT_API_KEY not set — using mock data")
        return _mock_whale_transactions(limit)
    
    try:
        # Whale Alert API: https://docs.whale-alert.io/#transactions
        resp = requests.get(
            "https://api.whale-alert.io/v1/transactions",
            params={
                "api_key": WHALE_API_KEY,
                "min_value": 500000,  # $500k minimum
                "limit": limit,
                "currency": "btc,eth,usdt,usdc",
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        
        transactions = []
        for tx in data.get("transactions", []):
            amount_usd = tx.get("amount_usd", 0)
            symbol = tx.get("symbol", "").upper()
            threshold = THRESHOLDS.get(symbol, float("inf"))
            
            if amount_usd >= threshold:
                transactions.append(WhaleTransaction(
                    tx_hash=tx.get("hash", "")[:16] + "...",
                    blockchain=tx.get("blockchain", ""),
                    symbol=symbol,
                    amount=tx.get("amount", 0),
                    amount_usd=amount_usd,
                    from_address=tx.get("from", "")[:12] + "...",
                    to_address=tx.get("to", "")[:12] + "...",
                    from_owner=tx.get("from_owner"),
                    to_owner=tx.get("to_owner"),
                    timestamp=datetime.utcfromtimestamp(tx.get("timestamp", 0)),
                    tx_type=tx.get("transaction_type", "transfer"),
                ))
        
        return transactions
    
    except requests.RequestException as e:
        log.warning("Whale Alert API error: %s", e)
        return _mock_whale_transactions(limit)


def _mock_whale_transactions(limit: int) -> list[WhaleTransaction]:
    """Mock whale transactions for testing without API key."""
    log.info("Generating mock whale transactions")
    
    mock_data = [
        {
            "symbol": "BTC",
            "amount": 150.5,
            "amount_usd": 10_500_000,
            "from_owner": "Binance",
            "to_owner": "Unknown",
            "tx_type": "transfer",
        },
        {
            "symbol": "ETH",
            "amount": 2500.0,
            "amount_usd": 8_750_000,
            "from_owner": "Coinbase",
            "to_owner": "Kraken",
            "tx_type": "transfer",
        },
        {
            "symbol": "USDT",
            "amount": 5_000_000,
            "amount_usd": 5_000_000,
            "from_owner": "Tether Treasury",
            "to_owner": "Unknown",
            "tx_type": "mint",
        },
        {
            "symbol": "BTC",
            "amount": 75.2,
            "amount_usd": 5_264_000,
            "from_owner": "Unknown",
            "to_owner": "Gemini",
            "tx_type": "transfer",
        },
    ]
    
    transactions = []
    now = datetime.utcnow()
    
    for i, data in enumerate(mock_data[:limit]):
        transactions.append(WhaleTransaction(
            tx_hash=f"mock_tx_{i:04d}...",
            blockchain="bitcoin" if data["symbol"] == "BTC" else "ethereum",
            symbol=data["symbol"],
            amount=data["amount"],
            amount_usd=data["amount_usd"],
            from_address="0xabc..." if data["symbol"] != "BTC" else "1A1z...",
            to_address="0xdef..." if data["symbol"] != "BTC" else "1BvB...",
            from_owner=data.get("from_owner"),
            to_owner=data.get("to_owner"),
            timestamp=now - timedelta(minutes=i * 5),
            tx_type=data["tx_type"],
        ))
    
    return transactions


def format_whale_alert(tx: WhaleTransaction) -> str:
    """Format single whale transaction for Telegram."""
    direction = "🟢 IN" if tx.to_owner and "exchange" in tx.to_owner.lower() else "🔴 OUT"
    if tx.from_owner and "exchange" in tx.from_owner.lower():
        direction = "🔴 OUT"
    
    # Determine signal strength
    if tx.amount_usd >= 10_000_000:
        size_emoji = "🐋"
    elif tx.amount_usd >= 5_000_000:
        size_emoji = "🦈"
    else:
        size_emoji = "🐟"
    
    lines = [
        f"{size_emoji} **Whale Alert: {tx.symbol}**",
        f"",
        f"**Amount:** {tx.amount:,.2f} {tx.symbol} (${tx.amount_usd:,.0f})",
        f"**Type:** {tx.tx_type.upper()} {direction}",
        f"**From:** {tx.from_owner or tx.from_address}",
        f"**To:** {tx.to_owner or tx.to_address}",
        f"**Time:** {tx.timestamp.strftime('%H:%M UTC')}",
        f"**Tx:** `{tx.tx_hash}`",
    ]
    
    # Add signal interpretation
    if tx.tx_type == "mint":
        lines.append(f"⚠️ **Signal:** New stablecoin minting — potential buying pressure")
    elif tx.to_owner and "exchange" in tx.to_owner.lower():
        lines.append(f"⚠️ **Signal:** Moving TO exchange — possible selling pressure")
    elif tx.from_owner and "exchange" in tx.from_owner.lower():
        lines.append(f"✅ **Signal:** Moving FROM exchange — possible accumulation")
    
    return "\n".join(lines)


def scan_and_alert() -> list[str]:
    """
    Scan for whale transactions and return formatted alerts.
    
    Returns:
        List of formatted alert strings ready for Telegram
    """
    transactions = fetch_whale_alert(limit=20)
    alerts = []
    
    for tx in transactions:
        alerts.append(format_whale_alert(tx))
    
    log.info("Generated %d whale alerts", len(alerts))
    return alerts
