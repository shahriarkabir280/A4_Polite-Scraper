import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from scraper.pipeline import extract_record, parse_price, clean_text


FIXTURE = """<article class='product_page'><h1>  A Book  </h1><div class='product_main'><p class='price_color'>£12.50</p><p class='availability'> In stock (3 available) </p><p class='star-rating Three'></p></div></article><div id='product_description'></div>"""


class ParserTests(unittest.TestCase):
    def test_price_normalization(self):
        self.assertEqual(parse_price("£51.77"), 51.77)

    def test_relative_url_is_absolute(self):
        from urllib.parse import urljoin
        self.assertEqual(urljoin("https://books.toscrape.com/catalogue/page-1.html", "../book/x/index.html"), "https://books.toscrape.com/book/x/index.html")

    def test_missing_description_is_null(self):
        record = extract_record(FIXTURE, "https://example.com/book", "https://example.com/page", "now")
        self.assertIsNone(record["description"])

    def test_duplicate_urls_are_removed(self):
        self.assertEqual(list(dict.fromkeys(["a", "a", "b"])), ["a", "b"])

    def test_malformed_fixture_raises(self):
        with self.assertRaises(ValueError):
            extract_record("<html></html>", "https://example.com/book", "https://example.com/page", "now")

    def test_whitespace_cleaning(self):
        self.assertEqual(clean_text("  many   spaces\n"), "many spaces")


if __name__ == "__main__":
    unittest.main()

