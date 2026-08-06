from __future__ import annotations

import json
from datetime import date, timedelta, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from xml.etree import ElementTree

from research_agent.sources.sec.sec_material_events import classify_material_event_text


DEFAULT_REGISTRY = Path(__file__).resolve().parents[2] / "config" / "official_ir_feeds.json"


class _ArticleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.hidden = 0
        self.capture = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in {"script", "style"}:
            self.hidden += 1
        elif not self.hidden and tag in {"p", "h1", "h2"}:
            self.capture += 1
            self.parts.append("\n")
        elif not self.hidden and self.capture and tag == "br":
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"}:
            self.hidden = max(0, self.hidden - 1)
        elif not self.hidden and tag in {"p", "h1", "h2"}:
            self.parts.append("\n")
            self.capture = max(0, self.capture - 1)

    def handle_data(self, data: str) -> None:
        if not self.hidden and self.capture:
            self.parts.append(data)

    def text(self) -> str:
        return " ".join("".join(self.parts).split())


def registered_official_ir_feeds(
    *,
    cik: str,
    registry_path: str | Path = DEFAULT_REGISTRY,
) -> list[str]:
    path = Path(registry_path)
    if not path.is_file():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    expected = str(int(cik)).zfill(10)
    for issuer in payload.get("issuers") or []:
        if str(issuer.get("cik") or "").zfill(10) != expected:
            continue
        return [
            str(url)
            for url in issuer.get("feeds") or []
            if _valid_https_url(str(url))
        ]
    return []


def build_official_ir_feed_payload(
    *,
    ticker: str,
    feed_urls: list[str],
    as_of_date: str,
    retrieved_at: str,
    user_agent: str,
    lookback_days: int = 120,
    fetcher: Callable[[str], bytes] | None = None,
) -> dict[str, Any]:
    as_of = date.fromisoformat(as_of_date)
    cutoff = as_of - timedelta(days=lookback_days)
    events: list[dict[str, Any]] = []
    checked: list[str] = []
    fetch = fetcher or (lambda url: _fetch(url, user_agent=user_agent))
    for feed_url in feed_urls:
        feed_host = urlsplit(feed_url).hostname or ""
        xml = fetch(feed_url)
        checked.append(feed_url)
        root = ElementTree.fromstring(xml)
        for item in root.findall(".//item"):
            title = _child_text(item, "title")
            link = _child_text(item, "link")
            description = _child_text(item, "description")
            published = _rss_date(_child_text(item, "pubDate"))
            if (
                published is None
                or published < cutoff
                or published > as_of
                or not _same_site_https(link, feed_host)
            ):
                continue
            candidate = f"{title}. {description}"
            classified = classify_material_event_text(candidate)
            if _material_title(title):
                parser = _ArticleTextParser()
                parser.feed(fetch(link).decode("utf-8", errors="replace"))
                article_classification = classify_material_event_text(parser.text())
                if article_classification is not None:
                    classified = article_classification
            if classified is None:
                continue
            event_type, generic_headline, summary = classified
            events.append(
                {
                    "event_type": event_type,
                    "date": published.isoformat(),
                    "headline": title or generic_headline,
                    "summary": summary,
                    "material": True,
                    "source_id": f"IR_{ticker.upper()}_{published.isoformat()}_{event_type.upper()}",
                    "source_type": "official_press_release",
                    "authority_rank": 1,
                    "url": link,
                    "retrieved_at": retrieved_at,
                }
            )
    deduped = {
        (event["date"], event["event_type"], event["url"]): event for event in events
    }
    ordered = sorted(deduped.values(), key=lambda event: (event["date"], event["url"]))
    return {
        "coverage_status": "available",
        "checked_at": retrieved_at,
        "window_start": cutoff.isoformat(),
        "window_end": as_of.isoformat(),
        "sources_checked": checked,
        "events": ordered,
    }


def _fetch(url: str, *, user_agent: str) -> bytes:
    request = Request(
        url,
        headers={
            "User-Agent": user_agent,
            "Accept": "application/rss+xml, application/xml, text/html;q=0.9",
        },
    )
    with urlopen(request, timeout=20) as response:
        return response.read()


def _child_text(item, name: str) -> str:
    node = item.find(name)
    return " ".join((node.text or "").split()) if node is not None else ""


def _rss_date(value: str) -> date | None:
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.date()


def _valid_https_url(value: str) -> bool:
    parsed = urlsplit(value)
    return parsed.scheme == "https" and bool(parsed.hostname) and not parsed.username


def _same_site_https(value: str, feed_host: str) -> bool:
    if not _valid_https_url(value):
        return False
    host = urlsplit(value).hostname or ""
    return host == feed_host or host.endswith("." + feed_host) or feed_host.endswith("." + host)


def _material_title(title: str) -> bool:
    folded = title.casefold()
    return any(
        token in folded
        for token in (
            "technology disruption",
            "cybersecurity",
            "cyber incident",
            "ransomware",
            "restoring",
            "recovery",
            "recall",
            "production suspension",
        )
    )
