"""Tests for Phase 4: Deribit, On-chain, LP strategies."""

from __future__ import annotations

import pytest

from deribit.analyzer import DeribitAnalyzer, BasisOpportunity
from onchain.monitor import OnChainMonitor, WhaleTransaction
from lp_yield.scanner import LPScanner, LPPool


# --------------------------------------------------------------------------- #
class TestDeribit:
    def test_singleton(self):
        a1 = DeribitAnalyzer()
        a2 = DeribitAnalyzer()
        assert a1 is not a2  # not singleton

    def test_stub_basis(self):
        analyzer = DeribitAnalyzer()
        opps = analyzer._stub_basis_opportunities("BTC")
        assert len(opps) == 2
        assert all(isinstance(o, BasisOpportunity) for o in opps)
        assert "BTC" in opps[0].symbol

    def test_stub_basis_eth(self):
        analyzer = DeribitAnalyzer()
        opps = analyzer._stub_basis_opportunities("ETH")
        assert len(opps) == 2
        assert "ETH" in opps[0].symbol

    def test_basis_attributes(self):
        analyzer = DeribitAnalyzer()
        opps = analyzer._stub_basis_opportunities("BTC")
        o = opps[0]
        assert o.basis_percent > 0
        assert o.confidence > 0
        assert o.signal in ("contango", "backwardation")


# --------------------------------------------------------------------------- #
class TestOnChain:
    def test_stub_whales_btc(self):
        monitor = OnChainMonitor()
        txs = monitor._stub_whales("BTC", 1_000_000)
        assert len(txs) == 3
        assert all(tx.blockchain == "BTC" for tx in txs)
        assert all(tx.value_usd >= 1_000_000 for tx in txs)

    def test_stub_whales_eth(self):
        monitor = OnChainMonitor()
        txs = monitor._stub_whales("ETH", 500_000)
        assert len(txs) == 3
        assert all(tx.blockchain == "ETH" for tx in txs)

    def test_whale_tx_fields(self):
        monitor = OnChainMonitor()
        txs = monitor._stub_whales("BTC", 1_000_000)
        tx = txs[0]
        assert tx.txid.startswith("stub_btc")
        assert tx.value_usd > 0
        assert tx.direction in ("inflow", "outflow", None)
        assert tx.fee > 0


# --------------------------------------------------------------------------- #
class TestLP:
    def test_stub_pools(self):
        scanner = LPScanner()
        pools = scanner._stub_pools()
        assert len(pools) == 3
        assert all(isinstance(p, LPPool) for p in pools)
        assert pools[0].protocol in ("uniswap_v3", "curve", "aave")

    def test_pool_fields(self):
        scanner = LPScanner()
        pools = scanner._stub_pools()
        p = pools[0]
        assert p.tvl_usd > 0
        assert p.apy >= 0
        assert 0 <= p.risk_score <= 1
        assert p.token0 and p.token1

    def test_risk_calculation(self):
        scanner = LPScanner()
        # High APY, low TVL
        risk = scanner._calculate_risk({"apyReward": 50}, 60, 5_000_000)
        assert 0.2 <= risk <= 0.7

    def test_find_best_pools(self):
        scanner = LPScanner()
        pools = scanner.find_best_pools(min_tvl_usd=100, top_n=5)
        assert len(pools) <= 5
        # Should be sorted by some criteria
        if len(pools) >= 2:
            assert all(p.risk_score <= 0.7 for p in pools)

    def test_lp_pool_priority(self):
        scanner = LPScanner()
        pools = scanner._stub_pools()
        # Low risk pool should rank higher
        low_risk = [p for p in pools if p.risk_score <= 0.05]
        assert len(low_risk) > 0
