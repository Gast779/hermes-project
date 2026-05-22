#!/usr/bin/env python3
"""Send crypto daily report to Telegram topic."""
import os, sys
from dotenv import load_dotenv

load_dotenv('/tmp/hermes_project/hermes_project/.env')
load_dotenv('/home/hermes/.hermes/.env', override=True)

sys.path.insert(0, '/tmp/hermes_project/hermes_project')
from scripts.notify_telegram import send_telegram

REPORT = (
    "🪙 Crypto Market Report — 2026-05-22 22:00 EEST\n\n"
    "*Загальний стан*\n"
    "• Total market cap: $2.64T (-1.08% за 24h)\n"
    "• 24h volume: $74.78B\n"
    "• BTC dominance: 58.14%\n"
    "• ETH dominance: 9.61%\n\n"
    "*Топ 10 монет*\n"
    "```\n"
    " Symbol      Price       24h     Volume\n"
    " ────────────────────────────────────────\n"
    " BTC         $76,442.00  -1.07%  $26.65B\n"
    " ETH         $2,097.80   -1.22%  $11.33B\n"
    " USDT        $0.998893   -0.01%  $47.57B\n"
    " BNB         $652.80     -0.32%  $747.33M\n"
    " XRP         $1.3500     -1.42%  $1.65B\n"
    " USDC        $0.999743   -0.00%  $12.21B\n"
    " SOL         $85.3500    -1.91%  $2.33B\n"
    " TRX         $0.362440   -0.48%  $545.33M\n"
    " FIGR_HELOC  $1.0310     +0.47%  $108.27M\n"
    " DOGE        $0.104169   -0.96%  $626.70M\n"
    "```\n\n"
    "*🚀 Top 24h gainers*\n"
    "```\n"
    " Symbol  Price        24h      Volume\n"
    " ──────────────────────────────────────\n"
    " RAIL    $2.5300      +66.05%  $3.69M\n"
    " BEAT    $1.2200      +61.14%  $70.47M\n"
    " GENIUS  $0.649548    +48.91%  $105.30M\n"
    " XYO     $0.00491194  +30.85%  $17.05M\n"
    " UB      $0.113260    +24.62%  $27.69M\n"
    " ALT     $0.00886335  +22.94%  $146.53M\n"
    " TAG     $0.00142215  +21.77%  $7.72M\n"
    " NEAR    $2.1700      +18.43%  $1.20B\n"
    " GUA     $1.4200      +16.59%  $10.46M\n"
    " BILL    $0.083949    +14.69%  $112.46M\n"
    "```\n\n"
    "*📉 Top 24h losers*\n"
    "```\n"
    " Symbol     Price        24h      Volume\n"
    " ─────────────────────────────────────────\n"
    " RIF        $0.050133    -32.53%  $5.14M\n"
    " NEX        $0.00000434  -23.01%  $50.79M\n"
    " BANANAS31  $0.010348    -20.81%  $19.44M\n"
    " BSB        $0.840386    -18.65%  $111.04M\n"
    " ARRR       $0.313013    -17.52%  $526.58K\n"
    " KITE       $0.198809    -14.94%  $47.55M\n"
    " SKYAI      $0.272727    -14.02%  $84.08M\n"
    " PROVE      $0.285305    -12.52%  $54.06M\n"
    " TROLL      $0.108910    -12.08%  $8.68M\n"
    " B          $0.265305    -11.82%  $12.60M\n"
    "```\n\n"
    "*🔥 Trending* (за пошуками на CoinGecko)\n"
    "NEAR, HYPE, GENIUS, PENGU, VVV, ONDO, BILL, NEX, SUI, ETH\n\n"
    "📊 Дані: CoinGecko. Звіт згенеровано автоматично Hermes Crypto Monitor."
)

ok = send_telegram(REPORT, chat_id="-1003792129186", message_thread_id=25)
print("STATUS: sent" if ok else "STATUS: failed")
