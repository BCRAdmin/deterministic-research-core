from research_agent.sources.ir.official_news_feed import (
    build_official_ir_feed_payload,
)


def test_official_ir_feed_discovers_incident_and_recovery_without_ticker_logic():
    feed_url = "https://investor.example.test/releases/rss"
    incident_url = "https://investor.example.test/releases/incident"
    recovery_url = "https://investor.example.test/releases/recovery"
    responses = {
        feed_url: f"""
            <rss><channel>
              <item><title>Technology disruption</title><link>{incident_url}</link>
                <pubDate>Thu, 16 Jul 2026 12:00:00 GMT</pubDate></item>
              <item><title>Progress in restoring operations</title><link>{recovery_url}</link>
                <pubDate>Mon, 27 Jul 2026 12:00:00 GMT</pubDate></item>
            </channel></rss>
        """.encode(),
        incident_url: (
            b"<html><p>Unauthorized access occurred in connection with a ransomware event. "
            b"Production operations were temporarily suspended.</p></html>"
        ),
        recovery_url: (
            b"<html><p>The issuer has resumed the majority of production and made "
            b"significant progress in restoring operations.</p></html>"
        ),
    }

    payload = build_official_ir_feed_payload(
        ticker="GENERIC",
        feed_urls=[feed_url],
        as_of_date="2026-08-05",
        retrieved_at="2026-08-05T12:00:00Z",
        user_agent="Room16 test@example.test",
        fetcher=responses.__getitem__,
    )

    assert [event["event_type"] for event in payload["events"]] == [
        "cyber_incident",
        "operational_recovery",
    ]
    assert all(event["source_type"] == "official_press_release" for event in payload["events"])


def test_official_ir_feed_rejects_cross_site_article_links():
    feed_url = "https://investor.example.test/releases/rss"
    foreign_url = "https://attacker.example.test/fake"
    feed = f"""
        <rss><channel><item><title>Ransomware incident</title><link>{foreign_url}</link>
        <pubDate>Thu, 16 Jul 2026 12:00:00 GMT</pubDate></item></channel></rss>
    """.encode()

    payload = build_official_ir_feed_payload(
        ticker="GENERIC",
        feed_urls=[feed_url],
        as_of_date="2026-08-05",
        retrieved_at="2026-08-05T12:00:00Z",
        user_agent="Room16 test@example.test",
        fetcher=lambda url: feed,
    )

    assert payload["events"] == []
