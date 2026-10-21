"""Small loopback-only HTTP adapter over WorkflowService; no external assets."""
import argparse
from collections import OrderedDict
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import secrets
from threading import Lock

from .application import WorkflowService
from .portal import PortalService

MAX_REQUEST_BYTES = 8192
ASSETS = Path(__file__).with_name("web_assets")


@dataclass(frozen=True)
class Response:
    status: int
    body: bytes
    content_type: str = "application/json; charset=utf-8"
    download: bool = False


def _json(status: int, value: object) -> Response:
    return Response(status, json.dumps(value, ensure_ascii=False).encode("utf-8"))


class WebApplication:
    """HTTP-independent routes, testable without network connections."""

    def __init__(self, service: WorkflowService | None = None, *, port: int = 8000,
                 portal: PortalService | None = None) -> None:
        self.service = service if service is not None else WorkflowService()
        self.portal = portal if portal is not None else PortalService(self.service)
        self.port = port
        self.token = secrets.token_urlsafe(32)
        self.results: OrderedDict[str, bytes] = OrderedDict()
        self.lock = Lock()

    def dispatch(self, method: str, path: str, headers: dict[str, str], body: bytes = b"") -> Response:
        headers = {k.lower(): v for k, v in headers.items()}
        hosts = (f"127.0.0.1:{self.port}", f"localhost:{self.port}")
        if headers.get("host") not in hosts:
            return _json(403, {"error": "Use the local server address."})
        if len(body) > MAX_REQUEST_BYTES:
            return _json(413, {"error": "Request too large."})
        if method == "GET" and path == "/":
            html = (ASSETS / "index.html").read_text(encoding="utf-8").replace("{{TOKEN}}", self.token)
            return Response(200, html.encode("utf-8"), "text/html; charset=utf-8")
        if method == "GET" and path == "/hamar-background.png":
            # Only a reviewed clean scenic image should activate has-scenic-image.
            image_path = ASSETS / "hamar-background.png"
            if not image_path.is_file() or image_path.stat().st_size > 12 * 1024 * 1024:
                return _json(404, {"error": "Scenic image is not available."})
            image = image_path.read_bytes()
            if not image.startswith(b"\x89PNG\r\n\x1a\n"):
                return _json(404, {"error": "Scenic image is not a PNG."})
            return Response(200, image, "image/png")
        if method == "GET" and path in ("/app.js", "/style.css"):
            kind = "text/javascript" if path.endswith(".js") else "text/css"
            return Response(200, (ASSETS / path[1:]).read_bytes(), kind + "; charset=utf-8")
        if method == "GET" and path == "/api/portal":
            return _json(200, self.portal.overview())
        if method == "GET" and path == "/api/sources":
            return _json(200, {"sources": self.service.sources(), "provider": self.service.provider,
                               "external_retrieval": self.service.enable_http})
        if method == "GET" and path.startswith("/api/results/"):
            if not secrets.compare_digest(headers.get("x-hamar-token", "").encode("utf-8"), self.token.encode("ascii")):
                return _json(403, {"error": "Invalid local session token."})
            run_id = path.removeprefix("/api/results/")
            with self.lock:
                payload = self.results.get(run_id)
            if payload is None:
                return _json(404, {"error": "Result not found or expired; run again."})
            return Response(200, payload, download=True)
        if method != "POST" or path not in ("/api/run", "/api/search", "/api/answer"):
            return _json(404 if method in ("GET", "POST") else 405, {"error": "Route not available."})
        if headers.get("origin") not in tuple("http://" + host for host in hosts):
            return _json(403, {"error": "Requests must originate from the local interface."})
        if not secrets.compare_digest(headers.get("x-hamar-token", "").encode("utf-8"), self.token.encode("ascii")):
            return _json(403, {"error": "Invalid local session token."})
        if headers.get("content-type", "").split(";", 1)[0].strip().lower() != "application/json":
            return _json(415, {"error": "Expected application/json."})
        if path in ("/api/search", "/api/answer"):
            return self._portal_request(path, body)
        try:
            request = json.loads(body.decode("utf-8"))
            if not isinstance(request, dict) or set(request) != {"source_id"}:
                raise ValueError("Select one approved source.")
            source_id = request["source_id"]
            if not isinstance(source_id, str) or source_id not in {s["id"] for s in self.service.sources()}:
                raise ValueError("Select one approved source.")
        except (ValueError, UnicodeError):
            return _json(400, {"error": "Select one approved source; expected a JSON source_id."})
        try:
            result = self.service.run(source_id)
            payload = result.to_json().encode("utf-8")
        except (OSError, ValueError, TypeError, KeyError, RuntimeError):
            return _json(422, {"error": "Workflow failed; no result was saved. Check the approved fixture and provider."})
        run_id = secrets.token_hex(16)
        with self.lock:
            self.results[run_id] = payload
            while len(self.results) > 16:
                self.results.popitem(last=False)
        return _json(200, {"run_id": run_id, "result": json.loads(payload)})


    def _portal_request(self, path: str, body: bytes) -> Response:
        from .search import validate_query
        from .categories import CATEGORY_IDS
        try:
            request = json.loads(body.decode("utf-8"))
            if not isinstance(request, dict) or set(request) - {"query", "category"} or "query" not in request:
                raise ValueError("Invalid search request")
            query, category = request["query"], request.get("category")
            validate_query(query)
            if category is not None and (not isinstance(category, str) or category not in CATEGORY_IDS):
                raise ValueError("Invalid category")
        except (ValueError, UnicodeError, TypeError):
            return _json(400, {"error": "Ugyldig s\u00f8k. Bruk korte temaord uten personopplysninger eller nettadresser."})
        try:
            if path == "/api/search":
                return _json(200, self.portal.search(query, category=category))
            answer = self.portal.answer(query, category=category)
        except (OSError, RuntimeError, ValueError, TypeError, KeyError):
            return _json(422, {"error": "Arbeidsflyten feilet. Ingen nye kilder ble hentet."})
        payload = json.dumps(answer, ensure_ascii=False).encode("utf-8")
        run_id = secrets.token_hex(16)
        with self.lock:
            self.results[run_id] = payload
            while len(self.results) > 16:
                self.results.popitem(last=False)
        return _json(200, {"run_id": run_id, "answer": answer})


def make_handler(app: WebApplication) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(10)

        def log_message(self, format, *args):
            # No request bodies, personal data or provider responses in access logs.
            pass

        def _send(self, response: Response) -> None:
            self.send_response(response.status)
            self.send_header("Content-Type", response.content_type)
            self.send_header("Content-Length", str(len(response.body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
            if response.download:
                self.send_header("Content-Disposition", 'attachment; filename="hamar-result.json"')
            self.end_headers()
            self.wfile.write(response.body)

        def _handle(self) -> None:
            lengths = self.headers.get_all("Content-Length", [])
            if self.headers.get("Transfer-Encoding") or len(lengths) > 1:
                self.close_connection = True
                self._send(_json(400, {"error": "Invalid request framing."}))
                return
            try:
                length = int(lengths[0]) if lengths else 0
                if length < 0 or length > MAX_REQUEST_BYTES:
                    raise ValueError()
            except ValueError:
                self.close_connection = True
                self._send(_json(413, {"error": "Invalid or oversized request body."}))
                return
            try:
                body = self.rfile.read(length)
            except OSError:
                self.close_connection = True
                self._send(_json(400, {"error": "Unable to read request."}))
                return
            if len(body) != length:
                self.close_connection = True
                self._send(_json(400, {"error": "Incomplete request body."}))
                return
            if len(self.headers.get_all("Host", [])) != 1:
                self._send(_json(403, {"error": "Invalid local Host."}))
                return
            self._send(app.dispatch(self.command, self.path, dict(self.headers), body))

        do_GET = _handle
        do_POST = _handle
        do_PUT = _handle
        do_DELETE = _handle
    return Handler


def create_server(*, port: int = 8000, service: WorkflowService | None = None,
                  portal: PortalService | None = None) -> ThreadingHTTPServer:
    app = WebApplication(service, port=port, portal=portal)
    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(app))
    app.port = server.server_port
    return server


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--catalog", type=Path, action="append", default=[], help="Offline reviewed catalog; repeat for multiple files")
    parser.add_argument("--approvals", type=Path, help="Individually reviewed page manifest; never enables live fetching")
    parser.add_argument("--empty-index", action="store_true", help="Start without synthetic demo documents")
    parser.add_argument("--provider", choices=("mock", "ollama"), default=None)
    parser.add_argument("--demo", action="store_true", help="Explicit offline synthetic demo only")
    parser.add_argument("--real-sources", action="store_true", help="Explicit real mode (also the default)")
    parser.add_argument("--model", help="Installed Ollama model")
    parser.add_argument("--ollama-timeout", type=float, default=45.0)
    parser.add_argument("--fallback-to-mock", action="store_true", help="Explicit, labeled fallback on Ollama failure")
    args = parser.parse_args(argv)
    if not 1 <= args.port <= 65535:
        parser.error("port must be between 1 and 65535")
    if args.real_sources and (args.demo or args.empty_index):
        parser.error("Real-source mode cannot use a synthetic demo or empty test index")
    real_mode = args.real_sources or not (args.demo or args.empty_index)
    portal = None
    try:
        if real_mode:
            if args.fallback_to_mock or args.provider == "mock":
                raise ValueError("Real-source mode refuses mock fallback")
            from .real_sources import create_municipal_service
            service = create_municipal_service(args.catalog or [Path("output/municipal-catalog.json")],
                args.approvals or Path("docs/approved-service-pages.json"), model=args.model, timeout=args.ollama_timeout)
            portal = PortalService(service, index=service.index)
        else:
            if args.catalog or args.approvals:
                raise ValueError("Use real-source mode for reviewed catalogs")
            from .runtime import create_service
            service = create_service(args.provider or "mock", model=args.model, timeout=args.ollama_timeout,
                                     fallback_to_mock=args.fallback_to_mock)
            if args.empty_index:
                from .search import SearchIndex
                portal = PortalService(service, index=SearchIndex())
    except (OSError, ValueError, TypeError, KeyError):
        parser.error("Provider/catalog validation failed; no synthetic fallback. Use --demo only for offline testing.")
    try:
        with create_server(port=args.port, service=service, portal=portal) as server:
            print(f"Hamar KommuneAgent: http://127.0.0.1:{server.server_port} (provider: {service.provider})", flush=True)
            server.serve_forever()
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
