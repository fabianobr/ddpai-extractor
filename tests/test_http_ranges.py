import unittest
import io
import tempfile
from pathlib import Path
from functools import partial
from src.processing.http_server import RangeHandler
from src.processing.http_server import parse_byte_range


class TestVideoByteRanges(unittest.TestCase):
    def test_valid_ranges(self):
        self.assertEqual(parse_byte_range('bytes=3-7', 10), (3, 7))
        self.assertEqual(parse_byte_range('bytes=7-', 10), (7, 9))
        self.assertEqual(parse_byte_range('bytes=-3', 10), (7, 9))
        self.assertEqual(parse_byte_range('bytes=7-100', 10), (7, 9))

    def test_invalid_ranges(self):
        for value in ('bytes=10-', 'bytes=5-4', 'bytes=0-1,3-4', 'bytes=-0'):
            with self.assertRaises(ValueError):
                parse_byte_range(value, 10)


class FakeConnection:
    def __init__(self, request):
        self.request = io.BytesIO(request)
        self.response = io.BytesIO()

    def makefile(self, mode, *args, **kwargs):
        return self.request

    def sendall(self, data):
        self.response.write(data)


class TestHttpRangeResponse(unittest.TestCase):
    def request(self, method, byte_range):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, 'video.mp4').write_bytes(b'0123456789')
            connection = FakeConnection((method + ' /video.mp4 HTTP/1.0\r\nRange: ' + byte_range + '\r\n\r\n').encode())
            handler = partial(RangeHandler, directory=directory)
            handler(connection, ('127.0.0.1', 1234), object())
            return connection.response.getvalue()

    def test_get_returns_exact_requested_bytes(self):
        response = self.request('GET', 'bytes=3-7')
        self.assertIn(b'206 Partial Content', response)
        self.assertIn(b'Content-Range: bytes 3-7/10', response)
        self.assertTrue(response.endswith(b'\r\n\r\n34567'))

    def test_head_returns_headers_without_body(self):
        response = self.request('HEAD', 'bytes=3-7')
        self.assertIn(b'Content-Length: 5', response)
        self.assertTrue(response.endswith(b'\r\n\r\n'))

    def test_unsatisfiable_range_returns_416(self):
        response = self.request('GET', 'bytes=10-')
        self.assertIn(b'416 Range Not Satisfiable', response)
        self.assertIn(b'Content-Range: bytes */10', response)
