"""Small loopback-only HTTP adapter over WorkflowService; no external assets."""
import argparse
from collections import OrderedDict
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import secrets
from threading import Lock
import time

from .application import WorkflowService
from .portal import PortalService
from .provider_registry import ProviderRegistry

MAX_REQUEST_BYTES = 8192
ASSETS = Path(__file__).with_name("web_assets")


@dataclass(frozen=True)
class Response:
    status: int
    body: bytes
    content_type: str = "application/json; charset=utf-8"
    download: bool = False


@dataclass
class ClientSession:
    topic_terms: tuple[str, ...] = ()
    turns: int = 0
    revision: int = 0
    last_seen: float = field(default_factory=time.monotonic)


SESSION_TTL_SECONDS = 2 * 60 * 60
MAX_SESSIONS = 64
MAX_CONVERSATION_TURNS = 8


def _json(status: int, value: object) -> Response:
    return Response(status, json.dumps(value, ensure_ascii=False).encode("utf-8"))


class WebApplication:
    """HTTP-independent routes, testable without network connections."""

    def __init__(self, service: WorkflowService | None = None, *, port: int = 8000,
                 portal: PortalService | None = None, service_factory=None,
                 provider_registry: ProviderRegistry | None = None) -> None:
        self.service = service if service is not None else WorkflowService()
        self.portal = portal if portal is not None else PortalService(self.service)
        self.port = port
        self.token = secrets.token_urlsafe(32)
        self.results: OrderedDict[str, bytes] = OrderedDict()
        self.result_owners: dict[str, str] = {}
        self.lock = Lock()
        self.sessions: OrderedDict[str, ClientSession] = OrderedDict(((self.token, ClientSession()),))
        self.service_factory = service_factory
        self.provider_registry = provider_registry

    def _new_page_token(self) -> str:
        token = secrets.token_urlsafe(32)
        with self.lock:
            self.sessions[token] = ClientSession()
            now = time.monotonic()
            for key in tuple(self.sessions):
                if now - self.sessions[key].last_seen > SESSION_TTL_SECONDS:
                    self.sessions.pop(key, None)
                    self._delete_owned_results(key)
            while len(self.sessions) > MAX_SESSIONS:
                expired, _ = self.sessions.popitem(last=False)
                self._delete_owned_results(expired)
        return token

    def _delete_owned_results(self, token: str) -> None:
        for run_id, owner in tuple(self.result_owners.items()):
            if owner == token:
                self.result_owners.pop(run_id, None)
                self.results.pop(run_id, None)

    def _session(self, token: str) -> ClientSession | None:
        if not isinstance(token, str) or len(token) > 128:
            return None
        try:
            token.encode("ascii")
        except UnicodeEncodeError:
            return None
        with self.lock:
            key = next((stored for stored in self.sessions if secrets.compare_digest(token, stored)), None)
            session = self.sessions.get(key) if key is not None else None
            if session is None or time.monotonic() - session.last_seen > SESSION_TTL_SECONDS:
                if key is not None:
                    self.sessions.pop(key, None)
                    self._delete_owned_results(key)
                return None
            session.last_seen = time.monotonic()
            self.sessions.move_to_end(key)
            return session

    def dispatch(self, method: str, path: str, headers: dict[str, str], body: bytes = b"") -> Response:
        headers = {k.lower(): v for k, v in headers.items()}
        hosts = (f"127.0.0.1:{self.port}", f"localhost:{self.port}")
        if headers.get("host") not in hosts:
            return _json(403, {"error": "Use the local server address."})
        if len(body) > MAX_REQUEST_BYTES:
            return _json(413, {"error": "Request too large."})
        if method == "GET" and path == "/":
            html = (ASSETS / "index.html").read_text(encoding="utf-8").replace("{{TOKEN}}", self._new_page_token())
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
        if method == "GET" and path == "/api/providers":
            if self.provider_registry is not None:
                try:
                    return _json(200, {"choices": self.provider_registry.choices()})
                except (OSError, RuntimeError, ValueError, TypeError):
                    return _json(503, {"choices": [], "error": "Provider availability could not be checked safely."})
            provider, _, model = self.service.provider.partition(":")
            return _json(200, {"choices": [{"provider": provider, "model": model or "mock",
                "label": self.service.provider, "processing": "local", "available": True, "reason": ""}]})
        if method == "GET" and path == "/api/sources":
            return _json(200, {"sources": self.service.sources(), "provider": self.service.provider,
                               "external_retrieval": self.service.enable_http})
        if method == "GET" and path.startswith("/api/results/"):
            token = headers.get("x-hamar-token", "")
            if self._session(token) is None:
                return _json(403, {"error": "Invalid local session token."})
            run_id = path.removeprefix("/api/results/")
            with self.lock:
                payload = self.results.get(run_id)
                owner = self.result_owners.get(run_id)
            if payload is None or owner is None or not secrets.compare_digest(owner, token):
                return _json(404, {"error": "Result not found or expired; run again."})
            return Response(200, payload, download=True)
        if method != "POST" or path not in ("/api/run", "/api/search", "/api/answer", "/api/conversation/reset"):
            return _json(404 if method in ("GET", "POST") else 405, {"error": "Route not available."})
        if headers.get("origin") not in tuple("http://" + host for host in hosts):
            return _json(403, {"error": "Requests must originate from the local interface."})
        token = headers.get("x-hamar-token", "")
        session = self._session(token)
        if session is None:
            return _json(403, {"error": "Invalid local session token."})
        if headers.get("content-type", "").split(";", 1)[0].strip().lower() != "application/json":
            return _json(415, {"error": "Expected application/json."})
        if path in ("/api/search", "/api/answer"):
            return self._portal_request(path, body, token, session)
        if path == "/api/conversation/reset":
            try:
                request = json.loads(body.decode("utf-8"))
                if request != {}:
                    raise ValueError
            except (ValueError, UnicodeError, TypeError):
                return _json(400, {"error": "Reset requires an empty JSON object."})
            with self.lock:
                session.topic_terms = ()
                session.turns = 0
                session.revision += 1
            return _json(200, {"reset": True})
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
            self.result_owners[run_id] = token
            while len(self.results) > 16:
                self.results.popitem(last=False)
        return _json(200, {"run_id": run_id, "result": json.loads(payload)})


    def _portal_request(self, path: str, body: bytes, token: str, session: ClientSession) -> Response:
        from .search import validate_query
        from .categories import CATEGORY_IDS
        selected_created = False
        with self.lock:
            request_revision = session.revision
        try:
            request = json.loads(body.decode("utf-8"))
            allowed = {"query", "category"} if path == "/api/search" else {"query", "category", "provider", "model"}
            if not isinstance(request, dict) or set(request) - allowed or "query" not in request:
                raise ValueError("Invalid search request")
            query, category = request["query"], request.get("category")
            prior_terms = session.topic_terms if session.turns < MAX_CONVERSATION_TURNS else ()
            validate_query(query, real_sources=True, allow_followup=bool(prior_terms))
            if category is not None and (not isinstance(category, str) or category not in CATEGORY_IDS):
                raise ValueError("Invalid category")
            selected_workflow = self.service
            if path == "/api/answer" and ("provider" in request or "model" in request):
                if not {"provider", "model"}.issubset(request) or self.provider_registry is None or self.service_factory is None:
                    raise ValueError("Provider selection is unavailable")
                self.provider_registry.require_choice(request["provider"], request["model"])
                selected_workflow = self.service_factory(request["provider"], request["model"])
                selected_created = True
        except (ValueError, UnicodeError, TypeError):
            return _json(400, {"error": "Ugyldig s\u00f8k. Bruk korte temaord uten personopplysninger eller nettadresser."})
        except (OSError, RuntimeError, KeyError):
            return _json(503, {"error": "Valgt leverand\u00f8r er ikke tilgjengelig. Ingen reserveleverand\u00f8r ble brukt."})
        try:
            if path == "/api/search":
                return _json(200, self.portal.search(query, category=category))
            answer = self.portal.answer(query, category=category, workflow_service=selected_workflow,
                                        prior_terms=prior_terms)
        except (OSError, RuntimeError, ValueError, TypeError, KeyError):
            return _json(422, {"error": "Arbeidsflyten feilet. Ingen nye kilder ble hentet."})
        finally:
            if selected_created:
                closer = getattr(selected_workflow, "close", None)
                if not callable(closer):
                    closer = getattr(getattr(selected_workflow, "summarizer", None), "client", None)
                    closer = getattr(closer, "close", None)
                if callable(closer):
                    closer()
        try:
            current_terms = validate_query(query, real_sources=True, allow_followup=bool(prior_terms))
        except ValueError:
            current_terms = []
        effective_terms = tuple(current_terms or prior_terms)
        with self.lock:
            if session.revision != request_revision:
                return _json(409, {"error": "Conversation changed while the answer was being prepared. Submit the question again."})
            if answer.get("answer_status") in {"evidence_checked", "demo"} and answer.get("result"):
                session.topic_terms = effective_terms[:16]
                session.turns = (session.turns + 1) if prior_terms else 1
            else:
                session.topic_terms = ()
                session.turns = 0
        answer["is_follow_up"] = bool(answer.get("is_follow_up", False))
        payload = json.dumps(answer, ensure_ascii=False).encode("utf-8")
        run_id = secrets.token_hex(16)
        with self.lock:
            self.results[run_id] = payload
            self.result_owners[run_id] = token
            while len(self.results) > 16:
                expired, _ = self.results.popitem(last=False)
                self.result_owners.pop(expired, None)
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
                  portal: PortalService | None = None, service_factory=None,
                  provider_registry: ProviderRegistry | None = None) -> ThreadingHTTPServer:
    app = WebApplication(service, port=port, portal=portal, service_factory=service_factory,
                         provider_registry=provider_registry)
    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(app))
    app.port = server.server_port
    return server


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--catalog", type=Path, action="append", default=[], help="Offline reviewed catalog; repeat for multiple files")
    parser.add_argument("--approvals", type=Path, help="Individually reviewed page manifest; never enables live fetching")
    parser.add_argument("--empty-index", action="store_true", help="Start without synthetic demo documents")
    parser.add_argument("--provider", choices=("mock", "ollama", "openai"), default=None)
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
    service_factory = None
    provider_registry = ProviderRegistry(include_mock=not (args.real_sources or not (args.demo or args.empty_index)))
    try:
        if real_mode:
            selected_provider = args.provider or "ollama"
            if args.fallback_to_mock or selected_provider == "mock":
                raise ValueError("Real-source mode refuses mock fallback")
            catalog_paths = args.catalog or [Path("output/municipal-catalog.json")]
            approval_path = args.approvals or Path("docs/approved-service-pages.json")
            from .real_sources import create_municipal_service
            service = create_municipal_service(catalog_paths, approval_path, model=args.model,
                timeout=args.ollama_timeout, provider=selected_provider)
            service_factory = lambda selected, model: create_municipal_service(
                catalog_paths, approval_path, model=model, timeout=args.ollama_timeout, provider=selected)
            portal = PortalService(service, index=service.index)
        else:
            if args.catalog or args.approvals:
                raise ValueError("Use real-source mode for reviewed catalogs")
            from .runtime import create_service
            service = create_service(args.provider or "mock", model=args.model, timeout=args.ollama_timeout,
                                     fallback_to_mock=args.fallback_to_mock)
            service_factory = lambda selected, model: create_service(
                selected, model=model, timeout=args.ollama_timeout, fallback_to_mock=False)
            if args.empty_index:
                from .search import SearchIndex
                portal = PortalService(service, index=SearchIndex())
    except (OSError, ValueError, TypeError, KeyError):
        parser.error("Provider/catalog validation failed; no synthetic fallback. Use --demo only for offline testing.")
    try:
        with create_server(port=args.port, service=service, portal=portal,
                           service_factory=service_factory, provider_registry=provider_registry) as server:
            print(f"Hamar KommuneAgent: http://127.0.0.1:{server.server_port} (provider: {service.provider})", flush=True)
            server.serve_forever()
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
