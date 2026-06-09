import json
from io import BytesIO
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError

import yourls


class YourlsTests(unittest.TestCase):
    def test_create_short_url_uses_handle_keyword(self):
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.read.return_value = json.dumps(
            {"shorturl": "https://short.example.com/sozcutv"}
        ).encode()

        with (
            patch.dict(
                yourls.os.environ,
                {
                    "YOURLS_API_URL": "http://yourls/yourls-api.php",
                    "YOURLS_USER": "user",
                    "YOURLS_PASS": "secret",
                    "PUBLIC_STREAM_BASE_URL": "https://stream.example.com",
                },
                clear=True,
            ),
            patch.object(yourls, "urlopen", return_value=response) as urlopen,
        ):
            result = yourls.create_short_url("sozcutv")

        self.assertEqual(result, "https://short.example.com/sozcutv")
        request = urlopen.call_args.args[0]
        self.assertIn(b"keyword=sozcutv", request.data)
        self.assertIn(
            b"url=https%3A%2F%2Fstream.example.com%2Fstream%3Fname%3Dsozcutv",
            request.data,
        )

    def test_missing_configuration_disables_shortening(self):
        with patch.dict(yourls.os.environ, {}, clear=True):
            self.assertIsNone(yourls.create_short_url("sozcutv"))

    def test_existing_long_url_reuses_short_url_from_http_400_response(self):
        body = BytesIO(
            json.dumps(
                {
                    "status": "fail",
                    "code": "error:url",
                    "shorturl": "https://short.example.com/szc",
                }
            ).encode()
        )
        error = HTTPError(
            "http://yourls/yourls-api.php",
            400,
            "Bad Request",
            {},
            body,
        )
        with (
            patch.dict(
                yourls.os.environ,
                {
                    "YOURLS_API_URL": "http://yourls/yourls-api.php",
                    "YOURLS_USER": "user",
                    "YOURLS_PASS": "secret",
                    "PUBLIC_STREAM_BASE_URL": "https://stream.example.com",
                },
                clear=True,
            ),
            patch.object(yourls, "urlopen", side_effect=error),
        ):
            self.assertEqual(
                yourls.create_short_url("sozcutv"),
                "https://short.example.com/szc",
            )


if __name__ == "__main__":
    unittest.main()
