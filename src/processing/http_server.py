"""Local static server with byte-range support for seeking large videos."""
import http.server
import os
import re
import shutil
import sys


class UnsatisfiableRange(ValueError):
    """Well-formed range that lies outside the file (answered with 416)."""


def parse_byte_range(value, size):
    """Return (start, end) inclusive.

    Raises UnsatisfiableRange for a valid range outside the file (416) and plain
    ValueError for a malformed/inverted/unsupported one, which per RFC 7233 must
    be ignored (serve the whole file with 200).
    """
    match = re.fullmatch(r'bytes=(\d*)-(\d*)', value.strip())
    if not match or match.group(1) == match.group(2) == '':
        raise ValueError('invalid range')
    first, last = match.groups()
    if not first:
        if int(last) <= 0 or not size:
            raise UnsatisfiableRange('unsatisfiable suffix range')
        return max(0, size - int(last)), size - 1
    start = int(first)
    if last and int(last) < start:
        raise ValueError('inverted range')
    if start >= size:
        raise UnsatisfiableRange('range starts beyond end of file')
    return start, min(int(last), size - 1) if last else size - 1


class RangeHandler(http.server.SimpleHTTPRequestHandler):
    def send_head(self):
        self.byte_range = None
        path = self.translate_path(self.path)
        header = self.headers.get('Range')
        if not header or not os.path.isfile(path):
            return super().send_head()
        try:
            stream = open(path, 'rb')
        except OSError:
            self.send_error(404, 'File not found')
            return None
        size = os.fstat(stream.fileno()).st_size
        try:
            start, end = parse_byte_range(header, size)
        except UnsatisfiableRange:
            stream.close()
            self.send_response(416)
            self.send_header('Content-Range', 'bytes */{}'.format(size))
            self.end_headers()
            return None
        except ValueError:
            # Malformed/inverted range-spec: RFC 7233 says to ignore it and serve 200.
            stream.close()
            return super().send_head()
        self.byte_range = (start, end)
        self.send_response(206)
        self.send_header('Content-Type', self.guess_type(path))
        self.send_header('Accept-Ranges', 'bytes')
        self.send_header('Content-Range', 'bytes {}-{}/{}'.format(start, end, size))
        self.send_header('Content-Length', str(end - start + 1))
        self.send_header('Last-Modified', self.date_time_string(os.fstat(stream.fileno()).st_mtime))
        self.end_headers()
        stream.seek(start)
        return stream

    def copyfile(self, source, outputfile):
        # Browsers abort range requests on every seek; that is normal, not an error.
        try:
            if self.byte_range is None:
                return shutil.copyfileobj(source, outputfile)
            remaining = self.byte_range[1] - self.byte_range[0] + 1
            while remaining:
                chunk = source.read(min(1024 * 1024, remaining))
                if not chunk:
                    break
                outputfile.write(chunk)
                remaining -= len(chunk)
        except (BrokenPipeError, ConnectionResetError):
            pass


if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    server = http.server.ThreadingHTTPServer(('127.0.0.1', port), RangeHandler)
    print('🎬 DDpai Dashboard → http://127.0.0.1:{}/web/'.format(port), flush=True)
    server.serve_forever()
