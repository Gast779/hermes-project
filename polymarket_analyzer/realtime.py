"""
Real-time моніторинг змін цін через WebSocket.

Polymarket CLOB надає публічний WS-канал:
    wss://ws-subscriptions-clob.polymarket.com/ws/market

Підписка типу `price_change` віддає дельти orderbook для перелічених token_id.
Документація: https://docs.polymarket.com/developers/CLOB/websocket/wss-overview
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections import defaultdict
from typing import Awaitable, Callable, Iterable

import websockets

log = logging.getLogger(__name__)


# Тип callback-а: викликається, коли по token_id зʼявилась нова найкраща ціна.
PriceChangeCallback = Callable[[str, float, float, dict], Awaitable[None] | None]
#                                  token_id, best_bid, best_ask, raw_msg


class PolymarketRealtime:
    """
    Subscribes to CLOB WS і викликає callback на значущі зміни.

    Приклад:
        async def on_change(token_id, bid, ask, msg):
            print(token_id, bid, ask)

        rt = PolymarketRealtime(token_ids=["123..."], callback=on_change)
        asyncio.run(rt.run())
    """

    def __init__(
        self,
        token_ids: Iterable[str],
        callback: PriceChangeCallback,
        *,
        ws_url: str = "wss://ws-subscriptions-clob.polymarket.com/ws/market",
        ping_interval: int = 20,
        reconnect_delay: int = 3,
    ):
        self.token_ids = list(set(token_ids))
        self.callback = callback
        self.ws_url = ws_url
        self.ping_interval = ping_interval
        self.reconnect_delay = reconnect_delay
        # last best per token: {token_id: (bid, ask)}
        self._last: dict[str, tuple[float | None, float | None]] = defaultdict(lambda: (None, None))
        self._stop = False

    def stop(self) -> None:
        self._stop = True

    async def run(self) -> None:
        while not self._stop:
            try:
                async with websockets.connect(
                    self.ws_url, ping_interval=self.ping_interval
                ) as ws:
                    sub_msg = {
                        "type": "MARKET",
                        "assets_ids": self.token_ids,
                    }
                    await ws.send(json.dumps(sub_msg))
                    log.info("WS subscribed to %s tokens", len(self.token_ids))

                    async for raw in ws:
                        if self._stop:
                            break
                        await self._handle(raw)

            except (websockets.ConnectionClosed, OSError) as e:
                log.warning("WS connection lost: %s — reconnecting in %ss", e, self.reconnect_delay)
                await asyncio.sleep(self.reconnect_delay)
            except Exception as e:        # noqa: BLE001
                log.exception("WS unexpected error: %s", e)
                await asyncio.sleep(self.reconnect_delay)

    async def _handle(self, raw: str) -> None:
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            return

        if isinstance(msg, list):
            for m in msg:
                await self._handle_single(m)
        else:
            await self._handle_single(msg)

    async def _handle_single(self, msg: dict) -> None:
        # Polymarket WS повертає різні типи: PRICE_CHANGE, BOOK, TICK_SIZE_CHANGE, ...
        evt = msg.get("event_type") or msg.get("type")
        if evt not in {"price_change", "PRICE_CHANGE", "book", "BOOK"}:
            return

        token_id = msg.get("asset_id") or msg.get("token_id") or msg.get("market")
        if not token_id:
            return

        bid = self._top_price(msg.get("bids") or msg.get("buys"))
        ask = self._top_price(msg.get("asks") or msg.get("sells"))
        prev_bid, prev_ask = self._last[token_id]
        if (bid, ask) == (prev_bid, prev_ask):
            return
        self._last[token_id] = (bid, ask)

        if bid is None or ask is None:
            return

        res = self.callback(token_id, bid, ask, msg)
        if asyncio.iscoroutine(res):
            await res

    @staticmethod
    def _top_price(side: list | None) -> float | None:
        if not side:
            return None
        try:
            return float(side[0].get("price"))
        except (AttributeError, KeyError, ValueError, TypeError):
            return None
