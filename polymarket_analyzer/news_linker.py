"""
News Linker — звʼязує новини зі світу з ринками Polymarket.

Логіка:
    1. Тягне заголовки з кількох RSS-фідів (Reuters, AP, CoinDesk, ...).
    2. Для кожного заголовка дістає keywords (NER-lite через прості евристики).
    3. Шукає ринки Polymarket, де ці keywords збігаються з question / slug / tags.
    4. Повертає список {news → matched_markets} зі скором релевантності.

Без важких NLP-моделей — лише difflib + tokenization. Цього достатньо,
щоб ловити «Trump speech today» → ринки з ключем "trump".

Для production-якості можна потім підключити spaCy NER або LLM-екстрактор.
"""
from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime
from difflib import SequenceMatcher
from email.utils import parsedate_to_datetime
from typing import Iterable

import httpx

from .client import Market, PolymarketClient

log = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Default feeds — політика, фінанси, крипта, технології
# --------------------------------------------------------------------------- #
DEFAULT_FEEDS = [
    # General / politics
    "https://feeds.reuters.com/reuters/topNews",
    "https://feeds.bbci.co.uk/news/world/rss.xml",
    "https://feeds.apnews.com/rss/apf-topnews",
    # Crypto
    "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "https://cointelegraph.com/rss",
    # Tech / AI
    "https://techcrunch.com/feed/",
]

# Стоп-слова — не використовуємо для матчингу
STOPWORDS = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "to", "of", "for", "in", "on", "at", "by", "with", "from", "as",
    "and", "or", "but", "if", "than", "that", "this", "these", "those",
    "it", "its", "he", "she", "they", "we", "you", "i", "his", "her",
    "their", "our", "your", "my", "says", "said", "say", "will", "would",
    "could", "should", "may", "might", "can", "has", "have", "had",
    "after", "before", "during", "over", "under", "new", "more", "less",
    "report", "reports", "news", "today", "yesterday", "amid",
}


# --------------------------------------------------------------------------- #
@dataclass
class NewsItem:
    title: str
    link: str
    source: str
    published: datetime | None
    summary: str = ""
    keywords: list[str] = field(default_factory=list)


@dataclass
class NewsMatch:
    news: NewsItem
    market: Market
    score: float                  # 0..1 — наскільки впевнено зіставлено


# --------------------------------------------------------------------------- #
# RSS-парсер (мінімалістичний — без feedparser, щоб не додавати залежність)
# --------------------------------------------------------------------------- #
class RSSReader:
    def __init__(self, timeout: float = 10.0, user_agent: str = "hermes-news/1.0"):
        self._http = httpx.Client(
            timeout=timeout,
            headers={"User-Agent": user_agent, "Accept": "application/rss+xml,application/xml,text/xml"},
            follow_redirects=True,
        )

    def fetch(self, url: str) -> list[NewsItem]:
        try:
            r = self._http.get(url)
            r.raise_for_status()
        except httpx.HTTPError as e:
            log.warning("RSS fetch failed for %s: %s", url, e)
            return []

        items: list[NewsItem] = []
        try:
            root = ET.fromstring(r.content)
        except ET.ParseError as e:
            log.warning("RSS parse failed for %s: %s", url, e)
            return []

        # RSS 2.0: rss > channel > item; Atom: feed > entry. Обробляємо обидва.
        for item in root.iter():
            tag = item.tag.split("}")[-1].lower()
            if tag not in {"item", "entry"}:
                continue
            title = _txt(item, "title")
            link = _txt(item, "link") or _attr_link(item)
            pub = _txt(item, "pubDate") or _txt(item, "published") or _txt(item, "updated")
            summary = _txt(item, "description") or _txt(item, "summary") or ""
            if not title or not link:
                continue
            items.append(NewsItem(
                title=_strip_html(title),
                link=link.strip(),
                source=_host(url),
                published=_parse_date(pub),
                summary=_strip_html(summary)[:500],
            ))
        return items

    def fetch_all(self, urls: Iterable[str]) -> list[NewsItem]:
        out: list[NewsItem] = []
        for u in urls:
            out.extend(self.fetch(u))
        # дедуп по link
        seen, deduped = set(), []
        for n in out:
            if n.link in seen:
                continue
            seen.add(n.link)
            deduped.append(n)
        # найсвіжіші зверху
        deduped.sort(key=lambda n: n.published or datetime.min, reverse=True)
        return deduped

    def close(self) -> None:
        self._http.close()


def _txt(elem: ET.Element, tag: str) -> str | None:
    """Знаходить дочірній елемент з суфіксом tag (ігноруючи namespace)."""
    for child in elem:
        if child.tag.split("}")[-1].lower() == tag.lower():
            return (child.text or "").strip() or None
    return None


def _attr_link(elem: ET.Element) -> str | None:
    """Atom <link href="..."/>"""
    for child in elem:
        if child.tag.split("}")[-1].lower() == "link":
            href = child.attrib.get("href")
            if href:
                return href
    return None


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text or "").strip()


def _host(url: str) -> str:
    m = re.match(r"https?://([^/]+)/", url + "/")
    return m.group(1) if m else url


def _parse_date(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return parsedate_to_datetime(s)
    except (TypeError, ValueError):
        try:
            return datetime.fromisoformat(s.replace("Z", "+00:00"))
        except ValueError:
            return None


# --------------------------------------------------------------------------- #
# Keyword extraction (lite)
# --------------------------------------------------------------------------- #
def extract_keywords(text: str, *, min_len: int = 3, max_count: int = 12) -> list[str]:
    """
    Дуже простий екстрактор: токенізація → фільтр стоп-слів → беремо capitalized
    словосполучення (як proxy для іменованих сутностей) + просто довгі слова.
    """
    if not text:
        return []
    # Виловлюємо capitalized n-grams (1..3 слова), як простий NER-сурогат
    ngrams = re.findall(r"\b([A-Z][a-zA-Z'\-]+(?:\s+[A-Z][a-zA-Z'\-]+){0,2})\b", text)
    # + всі довгі lowercase слова
    words = re.findall(r"\b[a-zA-Z'\-]{%d,}\b" % min_len, text.lower())
    bag = []
    for n in ngrams:
        n = n.strip()
        if n.lower() not in STOPWORDS and n not in bag:
            bag.append(n)
    for w in words:
        if w in STOPWORDS or w in bag:
            continue
        bag.append(w)
    return bag[:max_count]


# --------------------------------------------------------------------------- #
# Matcher
# --------------------------------------------------------------------------- #
class NewsLinker:
    """
    Звʼязує NewsItem-и з Market-ами Polymarket.

    Алгоритм:
        для кожної новини → keywords;
        для кожного ринку → пул слів (question + slug + tags);
        score = (% keyword-збігів) * fuzzy_question_similarity.
    """

    def __init__(
        self,
        pm_client: PolymarketClient,
        feeds: Iterable[str] | None = None,
        *,
        min_score: float = 0.25,
        max_markets: int = 300,
    ):
        self.pm = pm_client
        self.feeds = list(feeds) if feeds else DEFAULT_FEEDS
        self.min_score = min_score
        self.max_markets = max_markets
        self.reader = RSSReader()

    # ---------------------------------------------------------------- #
    def _market_bag(self, m: Market) -> set[str]:
        words = re.findall(r"[a-zA-Z][a-zA-Z'\-]+", f"{m.question} {m.slug} {' '.join(m.tags)}".lower())
        return {w for w in words if w not in STOPWORDS and len(w) >= 3}

    def _score(self, news: NewsItem, market: Market, mbag: set[str]) -> float:
        kw_lower = [k.lower() for k in news.keywords]
        if not kw_lower:
            return 0.0
        hits = sum(1 for k in kw_lower if any(t in mbag for t in re.split(r"\s+", k)))
        coverage = hits / max(1, len(kw_lower))
        title_sim = SequenceMatcher(None, news.title.lower(), market.question.lower()).ratio()
        # Coverage важливіша (0.7) ніж fuzzy similarity заголовка (0.3)
        return 0.7 * coverage + 0.3 * title_sim

    # ---------------------------------------------------------------- #
    def link(self) -> list[NewsMatch]:
        news = self.reader.fetch_all(self.feeds)
        for n in news:
            n.keywords = extract_keywords(f"{n.title}. {n.summary}")

        markets = self.pm.fetch_markets(active=True, closed=False, max_total=self.max_markets)
        bags = {m.id: self._market_bag(m) for m in markets}

        out: list[NewsMatch] = []
        for n in news:
            best: tuple[float, Market] | None = None
            for m in markets:
                s = self._score(n, m, bags[m.id])
                if s >= self.min_score and (best is None or s > best[0]):
                    best = (s, m)
            if best:
                out.append(NewsMatch(news=n, market=best[1], score=best[0]))
        out.sort(key=lambda x: x.score, reverse=True)
        return out

    def close(self) -> None:
        self.reader.close()


# --------------------------------------------------------------------------- #
# Markdown report
# --------------------------------------------------------------------------- #
def format_news_links(matches: Iterable[NewsMatch]) -> str:
    matches = list(matches)
    if not matches:
        return "_Жодних звʼязків новина↔ринок зараз немає._"
    lines = [
        "## 📰 News → Polymarket",
        "",
        f"Знайдено **{len(matches)}** збігів (поріг score ≥ 0.25).",
        "",
        "| Score | Новина | Ринок |",
        "|-------|--------|-------|",
    ]
    for m in matches[:20]:
        title = m.news.title[:60] + ("…" if len(m.news.title) > 60 else "")
        q = m.market.question[:60] + ("…" if len(m.market.question) > 60 else "")
        url_market = f"https://polymarket.com/event/{m.market.slug}" if m.market.slug else ""
        market_link = f"[{q}]({url_market})" if url_market else q
        news_link = f"[{title}]({m.news.link})"
        lines.append(f"| {m.score:.2f} | {news_link} | {market_link} |")
    return "\n".join(lines)
