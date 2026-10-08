# A4 - The Polite Scraper

A cache-first Python scraping pipeline built for the [FlyRank Internship](https://internship.flyrank.ai/), Week 4 Assignment A4. The project collects book data from the first three catalogue pages of [Books to Scrape](https://books.toscrape.com/), validates the records, stores clean JSON output, and reports what happened during each run.

The implementation focuses on production-minded scraper habits:

- classify the target before collecting data;
- identify the client with a clear user-agent;
- use timeouts, status checks, and a minimum request delay;
- cache responses so development does not repeatedly contact the site;
- validate untrusted HTML-derived data before storing it;
- isolate failures so one broken page does not stop the run; and
- produce an honest machine-readable run report.

## Assignment context

The target is Books to Scrape, a public sandbox created for scraping practice. The scraper processes exactly the first three catalogue pages and discovers book links through the catalogue's own pagination. It does not hardcode the 60 book URLs.

Before implementation, `robots.txt` was requested once. The site returned HTTP 404, so the run records `no robots file found` in `output/run-report.json`. A missing robots file is not treated as permission to scrape other sites.

I will not reuse this code on another site without checking that site's rules and terms first.

## Tech stack

- Python 3.10+
- Requests for HTTP requests
- Beautiful Soup for HTML parsing
- Pydantic for schema validation
- `unittest` for parser tests
- JSON files for output and run evidence

## Quick start

Create a virtual environment, install the dependencies, and run the scraper:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m scraper
```

The module can also be run after activating the virtual environment:

```bash
source .venv/bin/activate
python -m scraper
```

The first run downloads the catalogue and detail pages into `cache/`. Subsequent runs reuse those files and avoid unnecessary network requests. The cache is ignored by Git.

## Test the failure path

The `--inject-failure` option adds one deliberately invalid book URL. It proves that the pipeline reports the failure while preserving all valid records:

```bash
.venv/bin/python -m scraper --inject-failure
```

This test uses the local cache for valid pages and makes one controlled request for the fake URL.

## Output files

Every run writes three files under `output/`:

- `books.json` - validated and normalized book records;
- `errors.json` - failed or invalid pages with their URL and reason; and
- `run-report.json` - timestamps, duration, fetch/cache counts, record counts, and failures.

The latest clean run produced:

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

The deliberately injected failure run completed with 60 valid records and `failed_pages: 1`.

## Record schema

Each stored record contains the raw scraped values plus one normalized value:

- `title` - book title;
- `product_url` - absolute HTTPS URL and record identity;
- `price_text` - original displayed price, such as `£51.77`;
- `price_gbp` - numeric price, such as `51.77`;
- `availability_text` - original availability text;
- `rating_text` - rating label, such as `Three`;
- `description` - product description, or `null` when it is missing;
- `source_page` - catalogue page from which the book URL was discovered; and
- `fetched_at` - UTC timestamp for the detail-page fetch.

Pydantic rejects missing required fields, unexpected fields, non-HTTPS URLs, and invalid prices. Records that fail validation are written to `errors.json` and never enter `books.json`.

## Politeness and reliability rules

- User-agent: `FlyRankInternship-A9/1.0` with a repository contact URL.
- Timeout: 10 seconds per request.
- Delay: at least 500 ms between real requests.
- Status handling: only HTTP 200 responses are parsed.
- Retry policy: one retry for timeouts and HTTP 5xx responses; no retry for HTTP 403 or 404.
- Cache policy: cached pages are read locally and do not incur a delay.
- Deduplication: records are keyed by their canonical product URL, making reruns idempotent.
- Failure isolation: a failed detail page is logged and skipped while the remaining pages continue.

## Project structure

```text
.
├── scraper/
│   ├── __main__.py       # CLI entry point
│   └── pipeline.py       # fetch, discover, extract, validate, store, report
├── tests/
│   └── test_pipeline.py  # parser and normalization tests
├── output/               # sample JSON evidence committed to the repository
├── cache/                # local HTML cache, ignored by Git
├── requirements.txt
└── README.md
```

## Tests

Run the test suite with:

```bash
.venv/bin/python -m unittest discover -s tests -v
```

The tests cover price normalization, relative URL resolution, missing descriptions, duplicate URLs, malformed HTML, and whitespace cleanup.

## Why no browser is needed

The assignment data is present in the HTML returned by the server. A browser would add startup cost and memory usage without providing additional data, so a normal HTTP client is the appropriate tool for this pipeline.

## Ethics and limitation

Use an official API when one exists. Never bypass logins, paywalls, access controls, or blocks. Collect only the fields needed for the stated purpose. This project targets one known practice sandbox, and its CSS selectors may require maintenance if the sandbox's HTML changes.

## Git history

The repository follows the assignment's staged workflow with separate commits for target classification, fetching, discovery, extraction, validation, failure handling, and publishing evidence.
