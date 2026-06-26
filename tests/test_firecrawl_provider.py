import unittest
from unittest import mock

from web_search_plus_mcp import search


class FirecrawlCompatibleBackendTests(unittest.TestCase):
    def test_search_firecrawl_uses_custom_compatible_backend_url(self):
        fake_response = {
            "success": True,
            "data": {"web": [{"title": "Local backend result", "url": "https://example.com/local", "description": "Local compatible backend snippet"}]},
        }
        with mock.patch("web_search_plus_mcp.search.make_request", return_value=fake_response) as mock_request:
            result = search.search_firecrawl(
                query="local backend",
                api_key="fc-test-key-12345",
                api_url="http://127.0.0.1:8080/v2/search",
            )

        url, headers, body = mock_request.call_args.args[:3]
        self.assertEqual(url, "http://127.0.0.1:8080/v2/search")
        self.assertEqual(headers["Authorization"], "Bearer fc-test-key-12345")
        self.assertEqual(body["query"], "local backend")
        self.assertEqual(result["results"][0]["title"], "Local backend result")

    def test_extract_firecrawl_uses_custom_compatible_backend_url(self):
        fake_response = {
            "success": True,
            "data": {"markdown": "# Local backend\nClean content", "metadata": {"title": "Local backend page"}},
        }
        with mock.patch("web_search_plus_mcp.search.make_request", return_value=fake_response) as mock_request:
            result = search.extract_firecrawl(
                urls=["https://example.com"],
                api_key="fc-test-key-12345",
                api_url="http://127.0.0.1:8080/v2/scrape",
            )

        url, headers, body = mock_request.call_args.args[:3]
        self.assertEqual(url, "http://127.0.0.1:8080/v2/scrape")
        self.assertEqual(headers["Authorization"], "Bearer fc-test-key-12345")
        self.assertEqual(body["url"], "https://example.com")
        self.assertEqual(result["results"][0]["content"], "# Local backend\nClean content")


if __name__ == "__main__":
    unittest.main()
