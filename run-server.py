"""
BILAL FLIX - Local Streaming Server
====================================
Run this to stream movies from your OneDrive folder.
Opens BILAL FLIX in your browser with full streaming capability.

Usage:
  python run-server.py

Then open: http://localhost:8888/CLAUDE/Movies/index.html
"""

import http.server
import os
import sys
import webbrowser
import threading
import functools

PORT = 8888

# Serve from the "Seasons & Movies 2" root folder
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SERVE_DIR = os.path.dirname(os.path.dirname(SCRIPT_DIR))  # Go up 2 levels

# Custom handler that supports Range requests (needed for video seeking)
class RangeHTTPHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=SERVE_DIR, **kwargs)

    def do_GET(self):
        # Handle Range requests for video streaming
        range_header = self.headers.get('Range')
        if range_header:
            self.send_partial(range_header)
        else:
            super().do_GET()

    def send_partial(self, range_header):
        path = self.translate_path(self.path)
        if not os.path.isfile(path):
            self.send_error(404)
            return

        file_size = os.path.getsize(path)

        # Parse Range header: bytes=start-end
        try:
            ranges = range_header.replace('bytes=', '').split('-')
            start = int(ranges[0]) if ranges[0] else 0
            end = int(ranges[1]) if ranges[1] else file_size - 1
        except:
            start = 0
            end = file_size - 1

        if start >= file_size:
            self.send_error(416, 'Range Not Satisfiable')
            return

        end = min(end, file_size - 1)
        length = end - start + 1

        self.send_response(206)
        self.send_header('Content-Type', self.guess_type(path))
        self.send_header('Content-Range', f'bytes {start}-{end}/{file_size}')
        self.send_header('Content-Length', str(length))
        self.send_header('Accept-Ranges', 'bytes')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()

        with open(path, 'rb') as f:
            f.seek(start)
            remaining = length
            chunk_size = 64 * 1024
            while remaining > 0:
                chunk = f.read(min(chunk_size, remaining))
                if not chunk:
                    break
                self.wfile.write(chunk)
                remaining -= len(chunk)

    def guess_type(self, path):
        ext = os.path.splitext(path)[1].lower()
        types = {
            '.mp4': 'video/mp4',
            '.mkv': 'video/x-matroska',
            '.avi': 'video/x-msvideo',
            '.mov': 'video/quicktime',
            '.wmv': 'video/x-ms-wmv',
            '.webm': 'video/webm',
            '.m4v': 'video/mp4',
            '.srt': 'text/plain; charset=utf-8',
            '.vtt': 'text/vtt; charset=utf-8',
            '.ass': 'text/plain; charset=utf-8',
            '.sub': 'text/plain; charset=utf-8',
        }
        return types.get(ext, super().guess_type(path))

    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Headers', 'Range')
        super().end_headers()

    def log_message(self, format, *args):
        # Only log video requests, skip static files
        path = args[0] if args else ''
        if any(ext in str(path) for ext in ['.mp4', '.mkv', '.avi', '.mov', '.srt', '.vtt']):
            print(f"  Streaming: {path}")

def open_browser():
    """Open the browser after a short delay."""
    import time
    time.sleep(1.5)
    url = f'http://localhost:{PORT}/CLAUDE/Movies/index.html'
    webbrowser.open(url)
    print(f"\n  Browser opened: {url}")

def main():
    print()
    print("=" * 50)
    print("  BILAL FLIX - Local Streaming Server")
    print("=" * 50)
    print(f"\n  Serving from: {SERVE_DIR}")
    print(f"  Port: {PORT}")
    print(f"\n  App URL: http://localhost:{PORT}/CLAUDE/Movies/index.html")
    print(f"\n  Press Ctrl+C to stop the server")
    print("=" * 50)

    handler = RangeHTTPHandler

    try:
        server = http.server.HTTPServer(('', PORT), handler)
    except OSError:
        print(f"\n  Port {PORT} is busy. Trying {PORT + 1}...")
        server = http.server.HTTPServer(('', PORT + 1), handler)

    # Open browser in background
    threading.Thread(target=open_browser, daemon=True).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n\n  Server stopped.")
        server.server_close()

if __name__ == '__main__':
    main()
