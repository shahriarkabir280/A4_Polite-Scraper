# The polite scraper

A small, cache-first Python scraper for the first three catalogue pages of [Books to Scrape](https://books.toscrape.com/). It discovers the catalogue's own next links, visits each of the 60 book pages, extracts raw fields, normalizes and validates them, and writes a truthful run report.

## Target classification

The target is Books to Scrape, a public practice sandbox built for learning web scraping. The scope is exactly the first three catalogue pages (60 books). I collect only each book's title, canonical URL, displayed price, availability, rating, description, source page, and fetch timestamp. This is appropriate because the site is explicitly intended for practice, the data is already present in server HTML, and the scraper is deliberately slow and cache-first. I checked `https://books.toscrape.com/robots.txt`: it is available and was fetched once before scraping; this run records the result in `output/run-report.json`.

I will not reuse this code on another site without checking its rules and terms first.

## Run it

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m scraper
```

The first run downloads and caches HTML. Later development runs read cached pages and do not contact the site for those pages. To deliberately exercise failure handling without touching the site, run:

```bash
.venv/bin/python -m scraper --inject-failure
```

Outputs are `output/books.json`, `output/errors.json`, and `output/run-report.json`. Cached HTML is intentionally ignored by Git.

## Schema

Each valid record contains the eight raw fields `title`, `product_url`, `price_text`, `availability_text`, `rating_text`, `description`, `source_page`, and `fetched_at`, plus numeric `price_gbp`. `description` may be null. `product_url` is the canonical identity and must be HTTPS.

## Politeness and reliability

- Every real request uses an identifying user-agent, a 10-second timeout, and status-code checking.
- Real requests are separated by at least 500 ms.
- A timeout or 5xx response is retried once after a short wait; 403 and 404 are never retried.
- Development uses the local cache, and cache hits do not sleep.
- A single broken page is recorded in `errors.json` and cannot abort the run.
- Output is deduplicated by canonical URL, so reruns are idempotent.

## Evidence from a run

```json
{
  "catalogue_pages": 3,
  "discovered": 60,
  "unique_urls": 60,
  "detail_pages": 60,
  "valid_records": 60,
  "invalid_records": 0,
  "failed_pages": 0
}
```

The assignment needs no browser: the book data is already in the HTML sent by the server, so a browser would only add cost and complexity.

## Ethics and limitation

Use an official API when one exists. Never bypass logins, paywalls, or blocks, and collect only what is needed. This is a teaching scraper for one known sandbox; selectors may need updating if the sandbox changes.

## Tests

```bash
python3 -m unittest discover -s tests -v
```

