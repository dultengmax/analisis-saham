import unittest

from data.price_fetcher import _chart_to_history, _raise_yahoo_error


class PriceFetcherTestCase(unittest.TestCase):
    def test_yahoo_connection_error_is_readable(self):
        with self.assertRaisesRegex(ConnectionError, "Yahoo Finance tidak bisa diakses"):
            _raise_yahoo_error(Exception("curl: (7) Failed to connect to fc.yahoo.com"))

    def test_chart_to_history(self):
        df = _chart_to_history(
            {
                "timestamp": [1764205200, 1764291600],
                "indicators": {
                    "quote": [
                        {
                            "open": [100, 102],
                            "high": [105, 103],
                            "low": [99, 101],
                            "close": [104, 102],
                            "volume": [1000, 900],
                        }
                    ]
                },
            }
        )

        self.assertEqual(list(df.columns), ["Open", "High", "Low", "Close", "Volume"])
        self.assertEqual(len(df), 2)
        self.assertEqual(df.iloc[-1]["Close"], 102)


if __name__ == "__main__":
    unittest.main()
