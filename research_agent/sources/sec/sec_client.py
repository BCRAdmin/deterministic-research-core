from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
import gzip
from dataclasses import dataclass
from typing import Any, Dict, Optional

from research_agent.sources.sec.sec_cache import SecCache
from research_agent.sources.sec.sec_rate_limiter import SecRateLimiter


@dataclass
class SecClientConfig:
    user_agent: str
    base_url: str = "https://data.sec.gov"
    request_delay_seconds: float = 0.11
    timeout_seconds: int = 30
    max_retries: int = 3
    use_cache: bool = True
    cache_dir: str = "research_agent/data/cache/sec"
    cache_ttl_hours: int = 24


class SecClient:
    def __init__(self, config: SecClientConfig):
        if not config.user_agent or "@" not in config.user_agent:
            raise ValueError("SEC User-Agent must identify app/company and contact email.")
        self.config = config
        self.rate_limiter = SecRateLimiter(config.request_delay_seconds)
        self.cache = SecCache(config.cache_dir, config.cache_ttl_hours) if config.use_cache else None

    def get_json(self, path: str) -> Dict[str, Any]:
        if not path.startswith("/"):
            path = "/" + path
        cache_key = f"{self.config.base_url}{path}"
        if self.cache:
            cached = self.cache.get(cache_key)
            if cached is not None:
                return cached

        url = self.config.base_url.rstrip("/") + path
        last_error: Optional[Exception] = None
        for attempt in range(1, self.config.max_retries + 1):
            try:
                self.rate_limiter.wait()
                request = urllib.request.Request(
                    url,
                    headers={
                        "User-Agent": self.config.user_agent,
                        "Accept-Encoding": "gzip, deflate",
                        "Accept": "application/json",
                    },
                )
                with urllib.request.urlopen(request, timeout=self.config.timeout_seconds) as response:
                    raw = response.read()
                    if response.headers.get("Content-Encoding") == "gzip":
                        raw = gzip.decompress(raw)
                    payload = json.loads(raw.decode("utf-8"))
                if self.cache:
                    self.cache.set(cache_key, payload)
                return payload
            except urllib.error.HTTPError as exc:
                last_error = exc
                if exc.code == 429:
                    time.sleep(min(2**attempt, 10))
                    continue
                time.sleep(min(2**attempt, 10))
            except Exception as exc:
                last_error = exc
                time.sleep(min(2**attempt, 10))
        raise RuntimeError(f"SEC request failed after retries: {url}") from last_error

    def get_companyfacts(self, cik: str) -> Dict[str, Any]:
        cik10 = str(cik).zfill(10)
        return self.get_json(f"/api/xbrl/companyfacts/CIK{cik10}.json")

    def get_submissions(self, cik: str) -> Dict[str, Any]:
        cik10 = str(cik).zfill(10)
        return self.get_json(f"/submissions/CIK{cik10}.json")

    def get_company_tickers(self) -> Dict[str, Any]:
        """Return the official SEC ticker/CIK mapping.

        The mapping lives on www.sec.gov rather than data.sec.gov, so use a
        short-lived client with the same identity, retry, cache, and rate
        policies instead of bypassing the SEC access contract.
        """

        website_config = SecClientConfig(
            user_agent=self.config.user_agent,
            base_url="https://www.sec.gov",
            request_delay_seconds=self.config.request_delay_seconds,
            timeout_seconds=self.config.timeout_seconds,
            max_retries=self.config.max_retries,
            use_cache=self.config.use_cache,
            cache_dir=self.config.cache_dir,
            cache_ttl_hours=self.config.cache_ttl_hours,
        )
        return SecClient(website_config).get_json("/files/company_tickers.json")
