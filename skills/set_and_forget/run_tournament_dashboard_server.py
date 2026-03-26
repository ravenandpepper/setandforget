import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
DEFAULT_INDEX = "tournament_dashboard.html"


class DashboardHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store, max-age=0")
        super().end_headers()

    def do_GET(self):
        if self.path in {"", "/"}:
            self.path = f"/{DEFAULT_INDEX}"
        return super().do_GET()


def build_server(host: str, port: int, directory: Path):
    handler = partial(DashboardHandler, directory=str(directory))
    return ThreadingHTTPServer((host, port), handler)


def main():
    parser = argparse.ArgumentParser(description="Serve the Set & Forget tournament dashboard as static files.")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--directory", type=Path, default=BASE_DIR)
    args = parser.parse_args()

    server = build_server(args.host, args.port, args.directory)
    print(f"Serving tournament dashboard on http://{args.host}:{args.port}/{DEFAULT_INDEX}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping tournament dashboard server.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
