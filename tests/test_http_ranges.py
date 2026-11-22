import unittest
import io
import tempfile
from pathlib import Path
from functools import partial
from src.processing.http_server import RangeHandler
from src.processing.http_server import parse_byte_range, UnsatisfiableRange


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


    def test_malformed_or_inverted_ranges_are_ignored_not_unsatisfiable(self):
        # RFC 7233: an invalid range-spec is ignored (serve 200), it is not a 416.
        for value in ('bytes=10-5', 'bytes=5-4', 'bytes=20-5', 'bytes=-', 'bytes=abc',
                      'items=1-2', 'bytes=0-1,3-4'):
            with self.assertRaises(ValueError) as ctx:
                parse_byte_range(value, 10)
            self.assertNotIsInstance(ctx.exception, UnsatisfiableRange, value)

    def test_start_beyond_size_is_unsatisfiable(self):
        for value in ('bytes=10-', 'bytes=10-20', 'bytes=-0'):
            with self.assertRaises(UnsatisfiableRange):
                parse_byte_range(value, 10)


class FakeConnection:
    def __init__(self, request, fail_after=None, error=BrokenPipeError):
        self.request = io.BytesIO(request)
        self.response = io.BytesIO()
        self.calls = 0
        self.fail_after = fail_after
        self.error = error

    def makefile(self, mode, *args, **kwargs):
        return self.request

    def sendall(self, data):
        self.calls += 1
        if self.fail_after is not None and self.calls > self.fail_after:
            raise self.error('client went away')
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

    def test_inverted_range_is_ignored_and_serves_whole_file(self):
        response = self.request('GET', 'bytes=10-5')
        self.assertIn(b' 200 ', response.split(b'\r\n', 1)[0])
        self.assertNotIn(b'Content-Range', response)
        self.assertTrue(response.endswith(b'\r\n\r\n0123456789'))

    def test_range_start_beyond_end_still_416(self):
        self.assertIn(b'416 Range Not Satisfiable', self.request('GET', 'bytes=50-60'))

    def test_client_abort_while_sending_body_is_silent(self):
        for method_range, error in (('bytes=3-7', BrokenPipeError), ('bytes=3-7', ConnectionResetError),
                                    ('bytes=10-5', BrokenPipeError)):
            with tempfile.TemporaryDirectory() as directory:
                Path(directory, 'video.mp4').write_bytes(b'0123456789')
                request = ('GET /video.mp4 HTTP/1.0\r\nRange: ' + method_range + '\r\n\r\n').encode()
                connection = FakeConnection(request, fail_after=1, error=error)
                # Headers go out in the first sendall; the body write then fails.
                partial(RangeHandler, directory=directory)(connection, ('127.0.0.1', 1234), object())
                self.assertGreater(connection.calls, 1)
