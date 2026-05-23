"""
Hermes v2.0 — Polymarket Whale & Insider Detection Module
==========================================================

Виявлення підозрілих угод на Polymarket: інсайдерські ставки,
великі гроші, аномальні об'єми. Інтеграція з SQLite Knowledge Base.

Адресат: polymarket_analyzer агент
Telegram: Thread #35 (Whale Alerts)
Формат: EN -> UK (спочатку англійською, потім українським перекладом)
"""

import sqlite3
import requests
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Optional, List, Dict
import json


# ═══════════════════════════════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════════════════════════════

GAMMA_API = "https://gamma-api.polymarket.com"
DATA_API = "https://data-api.polymarket.com"
CLOB_API = "https://clob.polymarket.com"
POLYGON_RPC = "https://polygon-rpc.com"

KB_PATH = Path.home() / ".hermes" / "hermes_knowledge_base.db"

WHALE_ALERT_THRESHOLD = 0.70  # Composite score >= 70% = HIGH alert
VOLUME_SPIKE_MULTIPLIER = 5.0  # 5x average = spike
MIN_TRADE_USD = 1000  # Мінімальна угода для аналізу
FRESH_WALLET_MAX_AGE_HOURS = 24
FRESH_WALLET_MIN_TX = 5
NICHE_MARKET_MAX_VOLUME = 50000
PRE_RESOLUTION_HOURS = 24


# ═══════════════════════════════════════════════════════════════════
# Data Classes
# ═══════════════════════════════════════════════════════════════════

class SignalType(Enum):
    FRESH_WALLET = "fresh_wallet"
    UNUSUAL_SIZING = "unusual_sizing"
    PRE_RESOLUTION = "pre_resolution"
    VOLUME_SPIKE = "volume_spike"
    WALLET_CLUSTER = "wallet_cluster"
    NICHE_MARKET = "niche_market"
    NEWS_LEAD = "news_lead"
    CROSS_MARKET_WIN = "cross_market_win"
    P_VALUE_ANOMALY = "p_value_anomaly"
    STEALTH_ACCUMULATION = "stealth_accumulation"


class Severity(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class DetectionSignal:
    signal_type: SignalType
    triggered: bool
    weight: float
    details: Dict = field(default_factory=dict)


@dataclass
class WhaleAlert:
    composite_score: float  # 0.0 - 1.0
    severity: Severity
    market_question: str
    market_question_uk: str  # український переклад
    action: str  # BUY YES / BUY NO / SELL YES / SELL NO
    price: float
    trade_size_usd: float
    wallet_address: str
    wallet_age_hours: Optional[float]
    wallet_tx_count: Optional[int]
    market_daily_volume: float
    signals_triggered: List[DetectionSignal]
    hours_to_resolution: Optional[float]
    timestamp: datetime
    alert_message_en: str = ""
    alert_message_uk: str = ""


@dataclass
class VolumeSpikeAlert:
    market_question: str
    market_question_uk: str
    current_1h_volume: float
    avg_24h_volume: float
    spike_ratio: float
    top_wallets_concentration: float  # % volume from top-5 wallets
    news_correlation: str  # "before_news" | "after_news" | "no_news"
    timestamp: datetime


# ═══════════════════════════════════════════════════════════════════
# Knowledge Base Interface
# ═══════════════════════════════════════════════════════════════════

class KnowledgeBase:
    """Інтерфейс до SQLite Knowledge Base для агентів."""

    def __init__(self, db_path: Path = KB_PATH):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row

    def get_whale_methods(self) -> List[Dict]:
        """Отримати всі методи whale detection."""
        cursor = self.conn.execute(
            "SELECT * FROM whale_detection_methods ORDER BY severity_weight DESC"
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_api_reference(self, use_case: str = None) -> List[Dict]:
        """Отримати API endpoints."""
        if use_case:
            cursor = self.conn.execute(
                "SELECT * FROM polymarket_api_reference WHERE use_case LIKE ?",
                (f"%{use_case}%",)
            )
        else:
            cursor = self.conn.execute("SELECT * FROM polymarket_api_reference")
        return [dict(row) for row in cursor.fetchall()]

    def get_kelly_params(self, strategy_type: str) -> Dict:
        """Отримати параметри Kelly для стратегії."""
        cursor = self.conn.execute(
            "SELECT * FROM kelly_criterion_params WHERE strategy_type = ?",
            (strategy_type,)
        )
        row = cursor.fetchone()
        return dict(row) if row else {}

    def get_ambiguous_patterns(self) -> List[Dict]:
        """Отримати патерни неоднозначності для resolution risk."""
        cursor = self.conn.execute(
            "SELECT * FROM ambiguous_market_patterns ORDER BY risk_weight DESC"
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_security_patterns(self) -> List[Dict]:
        """Отримати патерни безпеки LLM."""
        cursor = self.conn.execute(
            "SELECT * FROM llm_security_patterns ORDER BY risk_score DESC"
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_circuit_breakers(self) -> List[Dict]:
        """Отримати thresholds circuit breakers."""
        cursor = self.conn.execute(
            "SELECT * FROM circuit_breaker_thresholds ORDER BY severity"
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_insider_signals(self) -> List[Dict]:
        """Отримати сигнали insider detection."""
        cursor = self.conn.execute(
            "SELECT * FROM insider_detection_signals ORDER BY weight_in_score DESC"
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_agent_instructions(self, agent_name: str) -> List[Dict]:
        """Отримати інструкції для агента."""
        cursor = self.conn.execute(
            "SELECT * FROM agent_instructions WHERE agent_name = ? ORDER BY priority",
            (agent_name,)
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_english_methods(self, cefr_level: str = None) -> List[Dict]:
        """Отримати методи вивчення англійської."""
        if cefr_level:
            cursor = self.conn.execute(
                "SELECT * FROM english_learning_methods WHERE cefr_level LIKE ? ORDER BY effectiveness_score DESC",
                (f"%{cefr_level}%",)
            )
        else:
            cursor = self.conn.execute(
                "SELECT * FROM english_learning_methods ORDER BY effectiveness_score DESC"
            )
        return [dict(row) for row in cursor.fetchall()]

    def close(self):
        self.conn.close()


# ═══════════════════════════════════════════════════════════════════
# Polymarket API Client
# ═══════════════════════════════════════════════════════════════════

class PolymarketClient:
    """Клієнт для Polymarket APIs."""

    def __init__(self, proxy: str = None):
        self.proxy = proxy
        self.session = requests.Session()
        if proxy:
            self.session.proxies = {"http": proxy, "https": proxy}

    def get_recent_trades(self, min_cash: float = 1000, limit: int = 500) -> List[Dict]:
        """Отримати нещодавні угоди >= min_cash USD."""
        # Використовуємо Data API з filterType=CASH
        url = f"{DATA_API}/trades"
        params = {
            "filterType": "CASH",
            "filterAmount": min_cash,
            "limit": limit,
            "takerOnly": "true",
        }
        try:
            resp = self.session.get(url, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            return data.get("data", [])
        except Exception as e:
            print(f"[ERROR] get_recent_trades: {e}")
            return []

    def get_market(self, market_id: str) -> Optional[Dict]:
        """Отримати деталі ринку."""
        url = f"{GAMMA_API}/markets/{market_id}"
        try:
            resp = self.session.get(url, timeout=10)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            print(f"[ERROR] get_market: {e}")
            return None

    def get_market_holders(self, condition_id: str) -> List[Dict]:
        """Отримати топ холдерів ринку."""
        url = f"{DATA_API}/holders"
        params = {"market": condition_id}
        try:
            resp = self.session.get(url, params=params, timeout=10)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            print(f"[ERROR] get_market_holders: {e}")
            return []

    def get_wallet_activity(self, address: str, limit: int = 100) -> List[Dict]:
        """Отримати активність гаманця."""
        url = f"{DATA_API}/activity"
        params = {"user": address, "limit": limit}
        try:
            resp = self.session.get(url, params=params, timeout=10)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            print(f"[ERROR] get_wallet_activity: {e}")
            return []

    def get_orderbook(self, token_id: str) -> Optional[Dict]:
        """Отримати order book для токена."""
        url = f"{CLOB_API}/book"
        params = {"token_id": token_id}
        try:
            resp = self.session.get(url, params=params, timeout=10)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            print(f"[ERROR] get_orderbook: {e}")
            return None


# ═══════════════════════════════════════════════════════════════════
# Wallet Analysis
# ═══════════════════════════════════════════════════════════════════

class WalletAnalyzer:
    """Аналіз гаманців на предмет підозрілої поведінки."""

    def __init__(self, client: PolymarketClient):
        self.client = client

    def get_wallet_age_hours(self, address: str) -> Optional[float]:
        """Отримати вік гаманця в годинах (через Polygon RPC або Data API)."""
        activity = self.client.get_wallet_activity(address, limit=1)
        if not activity:
            return None
        first_tx_time = activity[-1].get("timestamp") if activity else None
        if first_tx_time:
            age_seconds = datetime.utcnow().timestamp() - first_tx_time
            return age_seconds / 3600
        return None

    def get_wallet_tx_count(self, address: str) -> int:
        """Отримати кількість транзакцій гаманця."""
        activity = self.client.get_wallet_activity(address, limit=500)
        return len(activity)

    def is_fresh_wallet(self, address: str, trade_usd: float) -> tuple[bool, Dict]:
        """Перевірити чи є гаманець 'свіжим'."""
        age = self.get_wallet_age_hours(address)
        tx_count = self.get_wallet_tx_count(address)

        triggered = (
            age is not None
            and age < FRESH_WALLET_MAX_AGE_HOURS
            and tx_count < FRESH_WALLET_MIN_TX
            and trade_usd >= MIN_TRADE_USD
        )

        return triggered, {
            "wallet_age_hours": age,
            "wallet_tx_count": tx_count,
            "trade_usd": trade_usd,
        }

    def analyze_funding_source(self, address: str) -> Dict:
        """Аналіз джерела фінансування (проста евристика)."""
        # TODO: Implement через Polygon RPC + etherscan-like API
        return {"funding_source": "unknown", "linked_wallets": []}


# ═══════════════════════════════════════════════════════════════════
# Detection Engine
# ═══════════════════════════════════════════════════════════════════

class DetectionEngine:
    """Основний движок виявлення підозрілих угод."""

    def __init__(self, client: PolymarketClient, kb: KnowledgeBase):
        self.client = client
        self.kb = kb
        self.wallet_analyzer = WalletAnalyzer(client)

    def detect_fresh_wallet(self, trade: Dict) -> DetectionSignal:
        """Виявити свіжий гаманець з великою угодою."""
        address = trade.get("proxyWallet") or trade.get("owner", "")
        size = float(trade.get("size", 0)) * float(trade.get("price", 0))

        triggered, details = self.wallet_analyzer.is_fresh_wallet(address, size)

        return DetectionSignal(
            signal_type=SignalType.FRESH_WALLET,
            triggered=triggered,
            weight=0.25,
            details=details,
        )

    def detect_unusual_sizing(self, trade: Dict, market_volume: float) -> DetectionSignal:
        """Виявити несумірно велику угоду."""
        size = float(trade.get("size", 0)) * float(trade.get("price", 0))
        threshold = market_volume * 0.02 if market_volume > 0 else float("inf")
        triggered = size >= threshold and size >= MIN_TRADE_USD

        return DetectionSignal(
            signal_type=SignalType.UNUSUAL_SIZING,
            triggered=triggered,
            weight=0.20,
            details={"trade_size": size, "market_volume": market_volume, "threshold": threshold},
        )

    def detect_pre_resolution(self, trade: Dict, market: Dict) -> DetectionSignal:
        """Виявити угоду перед резолюцією."""
        end_date_str = market.get("endDate") or market.get("resolution_date")
        if not end_date_str:
            return DetectionSignal(SignalType.PRE_RESOLUTION, False, 0.30, {})

        try:
            end_date = datetime.fromisoformat(end_date_str.replace("Z", "+00:00"))
            hours_to_res = (end_date - datetime.utcnow()).total_seconds() / 3600
        except:
            return DetectionSignal(SignalType.PRE_RESOLUTION, False, 0.30, {})

        size = float(trade.get("size", 0)) * float(trade.get("price", 0))
        triggered = hours_to_res < PRE_RESOLUTION_HOURS and size >= 5000

        return DetectionSignal(
            signal_type=SignalType.PRE_RESOLUTION,
            triggered=triggered,
            weight=0.30,
            details={"hours_to_resolution": hours_to_res, "trade_size": size},
        )

    def detect_volume_spike(self, market_id: str, current_1h_vol: float, avg_24h_vol: float) -> DetectionSignal:
        """Виявити аномальний стрибок об'єму."""
        avg_hourly = avg_24h_vol / 24 if avg_24h_vol > 0 else 1
        ratio = current_1h_vol / avg_hourly if avg_hourly > 0 else 0
        triggered = ratio >= VOLUME_SPIKE_MULTIPLIER

        return DetectionSignal(
            signal_type=SignalType.VOLUME_SPIKE,
            triggered=triggered,
            weight=0.20,
            details={"ratio": ratio, "current_1h": current_1h_vol, "avg_hourly": avg_hourly},
        )

    def detect_niche_market(self, trade: Dict, market_volume: float) -> DetectionSignal:
        """Виявити великі ставки на малоліквідному ринку."""
        size = float(trade.get("size", 0)) * float(trade.get("price", 0))
        triggered = market_volume < NICHE_MARKET_MAX_VOLUME and size >= 5000

        return DetectionSignal(
            signal_type=SignalType.NICHE_MARKET,
            triggered=triggered,
            weight=0.15,
            details={"market_volume": market_volume, "trade_size": size},
        )

    def calculate_composite_score(self, signals: List[DetectionSignal]) -> float:
        """Розрахувати композитний suspicion score."""
        total_weight = sum(s.weight for s in signals)
        triggered_weight = sum(s.weight for s in signals if s.triggered)

        if total_weight == 0:
            return 0.0
        return triggered_weight / total_weight

    def analyze_trade(self, trade: Dict, market: Dict) -> Optional[WhaleAlert]:
        """Повний аналіз однієї угоди."""
        market_volume = market.get("volume_24hr", 0) or market.get("volume", 1)

        signals = [
            self.detect_fresh_wallet(trade),
            self.detect_unusual_sizing(trade, market_volume),
            self.detect_pre_resolution(trade, market),
            self.detect_niche_market(trade, market_volume),
            # TODO: detect_volume_spike (needs historical data)
            # TODO: detect_wallet_cluster (needs DBSCAN)
        ]

        score = self.calculate_composite_score(signals)

        if score < 0.35:  # Мінімальний поріг для реєстрації
            return None

        severity = (
            Severity.CRITICAL if score >= 0.85 else
            Severity.HIGH if score >= WHALE_ALERT_THRESHOLD else
            Severity.MEDIUM if score >= 0.40 else
            Severity.LOW
        )

        address = trade.get("proxyWallet") or trade.get("owner", "")
        wallet_age = self.wallet_analyzer.get_wallet_age_hours(address)
        wallet_tx = self.wallet_analyzer.get_wallet_tx_count(address)

        # Базовий alert
        alert = WhaleAlert(
            composite_score=score,
            severity=severity,
            market_question=market.get("question", "Unknown"),
            market_question_uk="",  # TODO: переклад через Grok API
            action=f"{trade.get('side', 'BUY')} {trade.get('outcome', 'YES')}",
            price=float(trade.get("price", 0)),
            trade_size_usd=float(trade.get("size", 0)) * float(trade.get("price", 0)),
            wallet_address=address,
            wallet_age_hours=wallet_age,
            wallet_tx_count=wallet_tx,
            market_daily_volume=market_volume,
            signals_triggered=[s for s in signals if s.triggered],
            hours_to_resolution=None,  # TODO: з detect_pre_resolution
            timestamp=datetime.utcnow(),
        )

        alert.alert_message_en = self._format_alert_en(alert)
        alert.alert_message_uk = self._format_alert_uk(alert)

        return alert

    def _format_alert_en(self, alert: WhaleAlert) -> str:
        """Форматування alert англійською."""
        signals_str = ", ".join(s.signal_type.value for s in alert.signals_triggered)
        return f"""[WHALE ALERT] Score: {alert.composite_score*100:.0f}% | Severity: {alert.severity.value.upper()}

Market: {alert.market_question}
Action: {alert.action} at ${alert.price:.3f}
Size: ${alert.trade_size_usd:,.0f} ({alert.trade_size_usd/max(alert.market_daily_volume,1)*100:.1f}% of daily volume)
Wallet: {alert.wallet_address[:10]}... (Age: {alert.wallet_age_hours:.1f}h, {alert.wallet_tx_count} lifetime txns)
Signals: {signals_str}
Time: {alert.timestamp.strftime('%Y-%m-%d %H:%M UTC')}"""

    def _format_alert_uk(self, alert: WhaleAlert) -> str:
        """Форматування alert українською."""
        signals_str = ", ".join(s.signal_type.value for s in alert.signals_triggered)
        return f"""---
[УКРАЇНСЬКИЙ ПЕРЕКЛАД]

[СИГНАЛ КИТА] Оцінка: {alert.composite_score*100:.0f}% | Рівень: {alert.severity.value.upper()}

Ринок: {alert.market_question_uk or alert.market_question}
Дія: {alert.action} за ${alert.price:.3f}
Розмір: ${alert.trade_size_usd:,.0f} ({alert.trade_size_usd/max(alert.market_daily_volume,1)*100:.1f}% від денного об'єму)
Гаманець: {alert.wallet_address[:10]}... (Вік: {alert.wallet_age_hours:.1f}год, {alert.wallet_tx_count} транзакцій)
Сигнали: {signals_str}
Час: {alert.timestamp.strftime('%Y-%m-%d %H:%M UTC')}"""


# ═══════════════════════════════════════════════════════════════════
# Alert Dispatcher
# ═══════════════════════════════════════════════════════════════════

class AlertDispatcher:
    """Відправка alerts у Telegram та інші канали."""

    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{bot_token}"

    def send_whale_alert(self, alert: WhaleAlert, thread_id: int = 35):
        """Відправити whale alert у Telegram (EN + UK)."""
        message = alert.alert_message_en + "\n\n" + alert.alert_message_uk
        return self._send_message(message, thread_id)

    def send_volume_spike_alert(self, alert: VolumeSpikeAlert, thread_id: int = 35):
        """Відправити volume spike alert."""
        message = f"""[VOLUME SPIKE] {alert.spike_ratio:.1f}x average

Market: {alert.market_question}
Current 1h Volume: ${alert.current_1h_volume:,.0f}
Avg Hourly Volume: ${alert.avg_24h_volume/24:,.0f}
Top-5 Wallets: {alert.top_wallets_concentration:.0f}% of volume
News Correlation: {alert.news_correlation}
Time: {alert.timestamp.strftime('%Y-%m-%d %H:%M UTC')}
"""
        return self._send_message(message, thread_id)

    def _send_message(self, text: str, thread_id: int = None) -> bool:
        """Відправити повідомлення в Telegram."""
        url = f"{self.base_url}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "HTML",
        }
        if thread_id:
            payload["message_thread_id"] = thread_id

        try:
            resp = requests.post(url, json=payload, timeout=10)
            return resp.ok
        except Exception as e:
            print(f"[ERROR] Telegram send failed: {e}")
            return False


# ═══════════════════════════════════════════════════════════════════
# Main Scanner
# ═══════════════════════════════════════════════════════════════════

class WhaleScanner:
    """Головний сканер підозрілих угод."""

    def __init__(self, proxy: str = None, bot_token: str = None, chat_id: str = None):
        self.client = PolymarketClient(proxy)
        self.kb = KnowledgeBase()
        self.engine = DetectionEngine(self.client, self.kb)
        self.dispatcher = AlertDispatcher(bot_token, chat_id) if bot_token and chat_id else None

    def scan_recent_trades(self, min_cash: float = 1000) -> List[WhaleAlert]:
        """Сканувати нещодавні угоди на предмет підозрілих."""
        trades = self.client.get_recent_trades(min_cash=min_cash)
        alerts = []

        for trade in trades:
            market_id = trade.get("market") or trade.get("conditionId")
            if not market_id:
                continue

            market = self.client.get_market(market_id)
            if not market:
                continue

            alert = self.engine.analyze_trade(trade, market)
            if alert and alert.composite_score >= WHALE_ALERT_THRESHOLD:
                alerts.append(alert)

                # Відправити alert
                if self.dispatcher:
                    self.dispatcher.send_whale_alert(alert)

        return alerts

    def run_continuous(self, interval_seconds: int = 30):
        """Безперервний моніторинг."""
        import time
        print(f"[WhaleScanner] Starting continuous scan (interval: {interval_seconds}s)")

        while True:
            try:
                alerts = self.scan_recent_trades()
                if alerts:
                    print(f"[WhaleScanner] {len(alerts)} HIGH alerts detected")
                time.sleep(interval_seconds)
            except KeyboardInterrupt:
                print("[WhaleScanner] Stopped by user")
                break
            except Exception as e:
                print(f"[WhaleScanner] Error: {e}")
                time.sleep(interval_seconds)


# ═══════════════════════════════════════════════════════════════════
# CLI Entry Point
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Hermes Whale Detector")
    parser.add_argument("--scan", action="store_true", help="One-time scan")
    parser.add_argument("--watch", action="store_true", help="Continuous monitoring")
    parser.add_argument("--interval", type=int, default=30, help="Scan interval (seconds)")
    parser.add_argument("--min-cash", type=float, default=1000, help="Min trade size USD")
    parser.add_argument("--proxy", type=str, default=None, help="HTTP/SOCKS5 proxy")
    parser.add_argument("--bot-token", type=str, default=None, help="Telegram bot token")
    parser.add_argument("--chat-id", type=str, default=None, help="Telegram chat ID")

    args = parser.parse_args()

    scanner = WhaleScanner(
        proxy=args.proxy,
        bot_token=args.bot_token,
        chat_id=args.chat_id,
    )

    if args.watch:
        scanner.run_continuous(args.interval)
    elif args.scan:
        alerts = scanner.scan_recent_trades(min_cash=args.min_cash)
        for alert in alerts:
            print(alert.alert_message_en)
            print(alert.alert_message_uk)
            print("-" * 60)
    else:
        parser.print_help()
