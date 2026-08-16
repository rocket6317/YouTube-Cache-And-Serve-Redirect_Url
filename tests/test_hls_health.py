import unittest
from unittest.mock import Mock, patch

import hls_health


class HlsHealthTests(unittest.TestCase):
    def setUp(self):
        hls_health.clear_health_cache()

    def test_validates_newest_media_segment(self):
        manifest = Mock()
        manifest.read.return_value = (
            b"#EXTM3U\n#EXTINF:2,\nhttps://media.test/old.ts\n"
            b"#EXTINF:2,\nhttps://media.test/current.ts\n"
        )
        manifest.__enter__ = Mock(return_value=manifest)
        manifest.__exit__ = Mock(return_value=False)
        segment = Mock(status=206)
        segment.read.return_value = b"x"
        segment.__enter__ = Mock(return_value=segment)
        segment.__exit__ = Mock(return_value=False)

        with patch.object(hls_health, "urlopen", side_effect=[manifest, segment]) as open_url:
            self.assertTrue(
                hls_health.youtube_stream_is_playable(
                    "https://manifest.googlevideo.com/live.m3u8"
                )
            )

        self.assertEqual(open_url.call_args_list[1].args[0].full_url, "https://media.test/current.ts")
        self.assertEqual(open_url.call_args_list[1].args[0].headers["Range"], "bytes=0-0")

    def test_rejects_non_m3u8_response(self):
        response = Mock()
        response.read.return_value = b"Access denied"
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)

        with patch.object(hls_health, "urlopen", return_value=response):
            self.assertFalse(
                hls_health.youtube_stream_is_playable(
                    "https://manifest.googlevideo.com/broken.m3u8"
                )
            )

    def test_caches_health_result(self):
        response = Mock()
        response.read.return_value = b"Access denied"
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)

        with patch.object(hls_health, "urlopen", return_value=response) as open_url:
            url = "https://manifest.googlevideo.com/broken.m3u8"
            self.assertFalse(hls_health.youtube_stream_is_playable(url))
            self.assertFalse(hls_health.youtube_stream_is_playable(url))

        open_url.assert_called_once()


if __name__ == "__main__":
    unittest.main()
