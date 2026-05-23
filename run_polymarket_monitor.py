import sys
from polymarket_analyzer import PolymarketClient, TopicMonitor, format_topic_report

with PolymarketClient() as client:
    mon = TopicMonitor(client, 'trump')
    report = mon.tick()

has_updates = bool(report.arbitrage or report.significant_changes)

if has_updates:
    text = format_topic_report(report)
else:
    text = "👁️ Моніторинг теми: змін не виявлено."

print(text)
print("HAS_UPDATES=" + str(has_updates), file=sys.stderr)
