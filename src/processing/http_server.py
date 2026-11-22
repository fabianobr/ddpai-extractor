"""Local static server with byte-range support for seeking large videos."""
import http.server
import os
import re
import shutil
import sys


def parse_byte_range(value, size):
    match = re.fullmatch(r'bytes=(\d*)-(\d*)', value.strip())
    if not match or not size:
        raise ValueError('invalid range')
    first, last = match.groups()
    if not first:
        if not last or int(last) <= 0:
            raise ValueError('invalid suffix range')
        return max(0, size - int(last)), size - 1
    start = int(first)
    end = min(int(last), size - 1) if last else size - 1
    if start >= size or end < start:
        raise ValueError('unsatisfiable range')
    return start, end


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
        except ValueError:
            stream.close()
            self.send_response(416)
            self.send_header('Content-Range', 'bytes */{}'.format(size))
            self.end_headers()
            return None
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
        if self.byte_range is None:
            return shutil.copyfileobj(source, outputfile)
        remaining = self.byte_range[1] - self.byte_range[0] + 1
        while remaining:
            chunk = source.read(min(1024 * 1024, remaining))
            if not chunk:
                break
            outputfile.write(chunk)
            remaining -= len(chunk)


if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    server = http.server.ThreadingHTTPServer(('127.0.0.1', port), RangeHandler)
    print('🎬 DDpai Dashboard → http://127.0.0.1:{}/web/'.format(port), flush=True)
    server.serve_forever()
