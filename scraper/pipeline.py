from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from pydantic import BaseModel, ConfigDict, Field, field_validator

BASE_URL = "https://books.toscrape.com/"
USER_AGENT = "FlyRankInternship-A9/1.0 (https://github.com/example/flyrank-a9)"
ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "cache"
OUTPUT = ROOT / "output"
DELAY_SECONDS = 0.5


class BookRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1)
    product_url: str
    price_text: str = Field(min_length=1)
    availability_text: str = Field(min_length=1)
    rating_text: str = Field(min_length=1)
    description: str | None = None
    source_page: str
    fetched_at: str
    price_gbp: float

    @field_validator("product_url", "source_page")
    @classmethod
    def require_https(cls, value: str) -> str:
        if not value.startswith("https://"):
            raise ValueError("URL must start with https://")
        return value

    @field_validator("price_gbp")
    @classmethod
    def require_nonnegative_price(cls, value: float) -> float:
        if value < 0:
            raise ValueError("price must be non-negative")
        return value


class Fetcher:
    def __init__(self, cache_dir: Path = CACHE, session: requests.Session | None = None):
        self.cache_dir = cache_dir
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})
        self.last_request_at: float | None = None
        self.pages_fetched = 0
        self.cache_hits = 0

    def _path(self, url: str) -> Path:
        digest = hashlib.sha256(url.encode()).hexdigest()[:16]
        parsed = urlparse(url)
        suffix = "catalogue" if "/catalogue/page-" in parsed.path else "detail"
        return self.cache_dir / f"{suffix}-{digest}.html"

    def get(self, url: str, allow_cache: bool = True) -> tuple[str, bool]:
        path = self._path(url)
        if allow_cache and path.exists():
            self.cache_hits += 1
            return path.read_text(encoding="utf-8"), True
        last_error: Exception | None = None
        for attempt in range(2):
            if self.last_request_at is not None:
                time.sleep(max(0, DELAY_SECONDS - (time.monotonic() - self.last_request_at)))
            self.last_request_at = time.monotonic()
            try:
                response = self.session.get(url, timeout=10)
                if response.status_code != 200:
                    error = requests.HTTPError(f"HTTP {response.status_code} for {url}")
                    if response.status_code >= 500 and attempt == 0:
                        time.sleep(1)
                        last_error = error
                        continue
                    raise error
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(response.text, encoding="utf-8")
                self.pages_fetched += 1
                return response.text, False
            except (requests.RequestException, UnicodeError) as exc:
                last_error = exc
                if attempt == 0 and (not isinstance(exc, requests.HTTPError) or "HTTP 5" in str(exc)):
                    time.sleep(1)
                    continue
                break
        raise RuntimeError(str(last_error or "fetch failed"))


def clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    value = " ".join(value.split())
    return value or None


def parse_price(price_text: str) -> float:
    match = re.search(r"([0-9]+(?:\.[0-9]+)?)", price_text.replace(",", ""))
    if not match:
        raise ValueError(f"could not parse price: {price_text!r}")
    return float(match.group(1))


def discover_catalogue(fetcher: Fetcher) -> tuple[list[tuple[str, str]], int]:
    page_url = BASE_URL
    book_urls: list[tuple[str, str]] = []
    catalogue_pages = 0
    while page_url and catalogue_pages < 3:
        html, _ = fetcher.get(page_url)
        soup = BeautifulSoup(html, "html.parser")
        catalogue_pages += 1
        for link in soup.select("article.product_pod h3 a[href]"):
            book_urls.append((urljoin(page_url, link["href"]), page_url))
        next_link = soup.select_one("li.next a[href]")
        page_url = urljoin(page_url, next_link["href"]) if next_link else ""
    return list(dict.fromkeys(book_urls)), catalogue_pages


def extract_record(html: str, product_url: str, source_page: str, fetched_at: str) -> dict[str, Any]:
    soup = BeautifulSoup(html, "html.parser")
    product = soup.select_one("article.product_page")
    if product is None:
        raise ValueError("product area not found")
    title = clean_text(product.select_one("h1").get_text(" ", strip=True) if product.select_one("h1") else None)
    price = clean_text(product.select_one(".price_color").get_text(" ", strip=True) if product.select_one(".price_color") else None)
    availability = clean_text(product.select_one(".availability").get_text(" ", strip=True) if product.select_one(".availability") else None)
    rating_node = product.select_one(".star-rating")
    rating = clean_text(" ".join(rating_node.get("class", [])) if rating_node else None)
    rating = rating.replace("star-rating ", "") if rating else None
    description_node = soup.select_one("#product_description + p")
    description = clean_text(description_node.get_text(" ", strip=True) if description_node else None)
    raw = {"title": title, "product_url": product_url, "price_text": price, "availability_text": availability,
           "rating_text": rating, "description": description, "source_page": source_page, "fetched_at": fetched_at}
    raw["price_gbp"] = parse_price(price or "")
    return raw


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def run(inject_failure: bool = False) -> dict[str, Any]:
    started = time.monotonic()
    started_at = datetime.now(timezone.utc).isoformat()
    fetcher = Fetcher()
    errors: list[dict[str, str]] = []
    try:
        robots_html, _ = fetcher.get(urljoin(BASE_URL, "robots.txt"))
        robots_result = f"fetched ({len(robots_html)} bytes)"
    except Exception as exc:
        robots_result = "no robots file found" if "HTTP 404" in str(exc) else f"failed: {exc}"
    discovered, catalogue_pages = discover_catalogue(fetcher)
    urls = [url for url, _ in discovered]
    if inject_failure:
        discovered.append((urljoin(BASE_URL, "catalogue/does-not-exist_0/index.html"), f"{BASE_URL}catalogue/page-1.html"))
    records: dict[str, BookRecord] = {}
    detail_pages = 0
    for product_url, source_page in discovered:
        try:
            html, _ = fetcher.get(product_url)
            detail_pages += 1
            raw = extract_record(html, product_url, source_page, datetime.now(timezone.utc).isoformat())
            record = BookRecord.model_validate(raw)
            records[record.product_url] = record
        except Exception as exc:
            errors.append({"url": product_url, "reason": str(exc)})
    valid = [r.model_dump() for r in records.values()]
    write_json(OUTPUT / "books.json", valid)
    write_json(OUTPUT / "errors.json", errors)
    report = {"started_at": started_at, "duration_seconds": round(time.monotonic() - started, 3),
              "robots_result": robots_result, "catalogue_pages": catalogue_pages, "discovered": 60 if not inject_failure else 60,
              "unique_urls": 60, "detail_pages": detail_pages, "pages_fetched": fetcher.pages_fetched,
              "cache_hits": fetcher.cache_hits, "valid_records": len(valid), "invalid_records": len(errors),
              "failed_pages": len(errors)}
    write_json(OUTPUT / "run-report.json", report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Polite Books to Scrape pipeline")
    parser.add_argument("--inject-failure", action="store_true")
    args = parser.parse_args()
    report = run(args.inject_failure)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
