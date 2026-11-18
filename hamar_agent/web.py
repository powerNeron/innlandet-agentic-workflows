"""Small loopback-only HTTP adapter over WorkflowService; no external assets."""
import argparse
from contextlib import nullcontext
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
from .provider_registry import ProviderRegistry, ProviderSelectionError
from .ollama_provider import OllamaError
from .openai_provider import OpenAIProviderError
from .real_sources import RealSourceError
from .source_updates import SourceRefreshError
from .research import ResearchError
from .run_control import RunStopped, run_scope, checkpoint, current_run, cleanup_provider
from .chat import ChatBackend, ChatError, ChatState, MAX_TURNS, PAGE_RATE, PROCESS_RATE, RATE_SECONDS

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
    chat: ChatState = field(default_factory=ChatState)
    municipality_id: str | None = None


SESSION_TTL_SECONDS = 2 * 60 * 60
MAX_SESSIONS = 64
MAX_CONVERSATION_TURNS = 8


def _json(status: int, value: object) -> Response:
    return Response(status, json.dumps(value, ensure_ascii=False).encode("utf-8"))


def _provider_failure(error, *, status=422):
    """Only allowlisted categories cross the HTTP boundary, never exception text."""
    messages = {
        "research_unavailable": ("Nettsøk er ikke tilgjengelig. Ingen nye opplysninger er bekreftet.", True),
        "research_no_sources": ("Vi har ikke godkjente kilder som dekker dette spørsmålet. Prøv å presisere temaet.", False),
        "research_source_expired": ("Kildegrunnlaget kan ikke brukes nå. Ingen nye opplysninger er bekreftet.", False),
        "research_external_not_approved": ("Disse kildene er ikke godkjent for ekstern AI. Velg lokal AI.", False),
        "research_source_invalid": ("En kilde kunne ikke kontrolleres. Ingen nytt svar ble publisert.", True),
        "research_source_conflict": ("Kildene gir motstridende opplysninger. Aisha kan ikke bekrefte svaret.", False),
        "research_claim_unsupported": ("Svaret kunne ikke knyttes til kildene. Ingen nytt svar ble publisert.", True),
        "research_permission_revoked": ("Søketillatelsen er ikke lenger gyldig. Ingen nytt svar ble publisert.", False),
        "research_municipality_unknown": ("Vi har ikke et godkjent kildegrunnlag for denne kommunen. Presiser kommunen eller se kommunens offisielle nettside.", False),
        "research_municipality_ambiguous": ("Hvilken kommune gjelder spørsmålet? Spør om én kommune om gangen.", False),
        "research_municipality_required": ("Hvilken kommune gjelder spørsmålet? Ta med kommunenavnet.", False),
        "research_registry_expired": ("Kommuneoversikten må kontrolleres på nytt. Ingen nytt svar ble publisert.", False),
        "research_no_official_sources": ("Vi fant ikke en godkjent kilde fra denne kommunen. Andre nettsider kan ikke bekrefte kommunens egne vilkår.", False),
        "research_source_limit": ("Spørsmålet krever flere kilder enn vi kan behandle nå. Prøv et mer avgrenset spørsmål.", False),
        "run_budget_exceeded": ("Aisha nådde grensen for dette svaret. Prøv et kortere spørsmål. Ingen nytt svar ble lagret.", False),
        "run_input_limit": ("Det er for mye informasjon å behandle på én gang. Prøv et kortere spørsmål.", False),
        "run_deadline_exceeded": ("Det tok for lang tid å lage svaret. Du kan prøve igjen senere. Behandlingen kan fortsette i bakgrunnen; ingen nytt svar blir lagret fra dette forsøket.", True),
        "run_source_timeout": ("En kilde svarte ikke i tide. Ingen nye opplysninger er bekreftet. Prøv igjen senere eller se kommunens nettside.", True),
        "run_capacity_exceeded": ("Aisha er opptatt akkurat nå. Vent litt og prøv igjen.", True),
        "run_configuration": ("Aisha må klargjøres av den som drifter tjenesten. Ingen forespørsel ble sendt til AI.", False),
        "run_closed": ("Kjøringen er avsluttet. Send et nytt spørsmål.", False),
        "run_provider_closed": ("AI-forbindelsen er avsluttet. Trykk Oppdater og prøv igjen.", True),
        "provider_authentication": ("Tilgangen til AI-leverandøren ble avvist. Be den som drifter tjenesten kontrollere serveroppsettet. Vanlig søk kan fortsatt brukes.", False),
        "provider_quota": ("AI-leverandørens bruksramme er nådd. Be den som drifter tjenesten kontrollere kontoen. Vanlig søk kan fortsatt brukes.", False),
        "provider_rate_limit": ("AI-leverandøren har nådd en bruksgrense. Vent litt før du prøver igjen. Ingen annen leverandør ble brukt.", True),
        "provider_timeout": ("AI-leverandøren brukte for lang tid. Prøv igjen senere, eller velg en annen tilgjengelig modell.", True),
        "provider_model_unavailable": ("Den valgte modellen kan ikke brukes nå. Oppdater modellvalgene og velg en tilgjengelig modell.", False),
        "provider_configuration": ("AI-oppsettet på serveren må kontrolleres av den som drifter tjenesten. Vanlig søk kan fortsatt brukes.", False),
        "provider_response_invalid": ("AI-leverandøren returnerte et svar som ikke kunne leses og kontrolleres. Ingen nytt svar ble publisert.", True),
        "provider_response_incomplete": ("AI-svaret ble avbrutt før det var ferdig. Prøv et kortere spørsmål. Ingen nytt svar ble lagret.", True),
        "provider_selection_invalid": ("Velg et tilgjengelig AI-alternativ. Trykk Oppdater hvis listen er utdatert.", False),
        "provider_unavailable": ("Kan ikke kontakte den valgte AI-leverandøren nå. Prøv igjen senere. Ingen reserveleverandør ble brukt.", True),
    }
    code = getattr(error, "code", None)
    if not isinstance(code, str) or code not in messages:
        return _json(status, {"error": "Arbeidsflyten feilet. Ingen nytt kildekontrollert svar ble lagret.", "error_code": "workflow_failed", "retryable": True})
    message, retryable = messages[code]
    return _json(429 if code == "provider_rate_limit" else status,
                 {"error": message, "error_code": code, "retryable": retryable})


def _source_failure(error):
    codes={'source_unavailable','source_approval_required','source_access_not_authorized',
           'source_response_invalid','source_budget_exhausted','source_changed_review_required',
           'source_request_mismatch','source_snapshot_incomplete','source_snapshot_modified'}
    code=error.code if error.code in codes else 'source_unavailable'
    return _json(503,{'error':'Vi kunne ikke kontrollere kommunens kilder nå. Ingen nye opplysninger er bekreftet. Prøv igjen senere eller se kommunens nettside.',
        'error_code':code,'retryable':code in ('source_unavailable','source_response_invalid')})


def _check_source_binding(value):
    check=getattr(value,'assert_publishable',None)
    if callable(check):
        check()


def _source_publication_guard(value):
    guard=getattr(value,'publication_guard',None)
    return guard() if callable(guard) else nullcontext()


def _chat_failure(error):
    messages = {
        'chat_invalid_message': 'Skriv en melding på 1–1000 tegn uten kontrolltegn.',
        'chat_invalid_request': 'Chatforespørselen er ugyldig. Oppdater siden og prøv igjen.',
        'chat_privacy': 'Ikke skriv personopplysninger, kontaktdata, passord eller API-nøkler i chatten.',
        'chat_paid_disabled': 'OpenAI er ikke aktivert her. Velg Lokal AI (Ollama) hvis den er tilgjengelig.',
        'chat_advanced_disabled': 'Utvidet AI er ikke aktivert. Velg et annet AI-alternativ.',
        'chat_search_unavailable': 'Nettsøk er ikke godkjent eller støttet for denne leverandøren. Slå av nettsøk.',
        'chat_stale': 'Samtalen er endret. Last inn samtalen på nytt før du prøver igjen.',
        'chat_busy': 'Aisha arbeider fortsatt med forrige melding. Vent litt før du prøver igjen.',
        'chat_rate_limit': 'Chatgrensen er nådd. Vent ett minutt før du prøver igjen.',
        'chat_turn_limit': 'Start en ny samtale for å fortsette. De tidligere meldingene sendes da ikke videre.',
        'chat_reset_required': 'Nullstill samtalen før du bytter leverandør, modell eller nettsøk.',
    }
    if error.code not in messages:
        return _provider_failure(error, status=error.status)
    return _json(error.status, {'error': messages[error.code], 'error_code': error.code,
                                'retryable': error.code in ('chat_busy', 'chat_rate_limit')})


class WebApplication:
    """HTTP-independent routes, testable without network connections."""

    def __init__(self, service: WorkflowService | None = None, *, port: int = 8000,
                 portal: PortalService | None = None, service_factory=None,
                 provider_registry: ProviderRegistry | None = None, chat_backend=None) -> None:
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
        self.chat_backend = chat_backend if chat_backend is not None else ChatBackend()

    def _configured_service_choice(self):
        """Describe only the already constructed service; never probe a provider."""
        provider, _, model = self.service.provider.partition(":")
        model = model or ("mock" if provider == "mock" else "")
        selectable = provider in {"mock", "ollama", "openai"} and bool(model) and self.service_factory is None
        return {"provider": provider, "model": model, "label": self.service.provider,
                "processing": "external" if provider == "openai" else "local" if provider in {"mock", "ollama"} else "unknown",
                "available": selectable, "availability_status": "synthetic" if provider == "mock" else "configured" if selectable else "disabled",
                "connection_status": "not_applicable" if provider == "mock" else "not_checked", "generation_verified": False,
                "reason": "Syntetisk demo, ikke en ekte språkmodell." if provider == "mock" else "Serverens valgte modell er konfigurert; tilkobling er ikke testet." if selectable else "Modellvalg er ikke konfigurert for denne serveren."}

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

    def _can_publish(self, token: str, session: ClientSession, revision: int) -> bool:
        """Caller holds self.lock through this check and result publication."""
        checkpoint('publication')
        return (self.sessions.get(token) is session and session.revision == revision
                and time.monotonic() - session.last_seen <= SESSION_TTL_SECONDS)

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
        if method == 'POST' and path == '/api/chat':
            try:
                with run_scope(self.chat_backend.policy()):
                    return self._dispatch(method, path, headers, body)
            except RunStopped as error:
                return _provider_failure(error)
            except ValueError:
                return _provider_failure(RunStopped('run_configuration'), status=503)
        if method == 'POST' and path in ('/api/run', '/api/answer', '/api/search'):
            try:
                with run_scope(getattr(self.service, 'run_policy', None)):
                    return self._dispatch(method, path, headers, body)
            except RunStopped as error:
                return _provider_failure(error)
            except SourceRefreshError as error:
                return _source_failure(error)
            except ValueError:
                return _provider_failure(RunStopped('run_configuration'), status=503)
        return self._dispatch(method, path, headers, body)

    def _dispatch(self, method: str, path: str, headers: dict[str, str], body: bytes = b"") -> Response:
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
        if method == "GET" and path == "/favicon.ico":
            icon_path = ASSETS / "favicon.ico"
            if not icon_path.is_file() or icon_path.stat().st_size > 64 * 1024:
                return _json(404, {"error": "Project icon is not available."})
            icon = icon_path.read_bytes()
            if not icon.startswith(b"\x00\x00\x01\x00"):
                return _json(404, {"error": "Project icon is not a valid ICO."})
            return Response(200, icon, "image/vnd.microsoft.icon")
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
            return _json(200, {"choices": [self._configured_service_choice()]})
        if method == "GET" and path == "/api/sources":
            return _json(200, {"sources": self.service.sources(), "provider": self.service.provider,
                               "external_retrieval": self.service.enable_http})
        if method == 'GET' and path == '/api/chat/options':
            return _json(200, {'choices': self.chat_backend.choices(), 'web_search_allowed': self.chat_backend.search_allowed(),
                               'max_turns': MAX_TURNS, 'max_message_chars': 1000, 'max_context_bytes': 12000,
                               'max_model_calls': 1, 'max_output_tokens': 512, 'page_requests_per_minute': PAGE_RATE,
                               'process_requests_per_minute': PROCESS_RATE, 'verified_municipal_answers': False})
        if method == 'GET' and path == '/api/chat/state':
            session = self._session(headers.get('x-hamar-token', ''))
            if session is None:
                return _json(403, {'error': 'Invalid local session token.'})
            with self.lock:
                return _json(200, {'messages': session.chat.display, 'revision': session.chat.revision,
                                   'turns': session.chat.turns, 'busy': session.chat.pending is not None})
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
        if method != "POST" or path not in ("/api/run", "/api/search", "/api/answer", "/api/conversation/reset", '/api/chat', '/api/chat/reset'):
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
        if path == '/api/chat':
            return self._chat_request(body, token, session)
        if path == '/api/chat/reset':
            try:
                if json.loads(body.decode('utf-8')) != {}:
                    raise ValueError
            except (ValueError, UnicodeError):
                return _json(400, {'error': 'Reset requires an empty JSON object.'})
            with self.lock:
                session.chat.messages = session.chat.display = ()
                session.chat.turns = 0
                session.chat.selection = None
                session.chat.revision += 1
                return _json(200, {'reset': True, 'revision': session.chat.revision,
                                   'busy': session.chat.pending is not None})
        if path == "/api/conversation/reset":
            try:
                request = json.loads(body.decode("utf-8"))
                if request != {}:
                    raise ValueError
            except (ValueError, UnicodeError, TypeError):
                return _json(400, {"error": "Reset requires an empty JSON object."})
            with self.lock:
                session.topic_terms = ()
                session.municipality_id = None
                session.turns = 0
                session.revision += 1
            return _json(200, {"reset": True})
        with self.lock:
            request_revision = session.revision
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
        except SourceRefreshError:
            raise
        except (OSError, ValueError, TypeError, KeyError, RuntimeError):
            return _json(422, {"error": "Workflow failed; no result was saved. Check the approved fixture and provider."})
        run_id = secrets.token_hex(16)
        response = _json(200, {"run_id": run_id, "result": json.loads(payload)})
        with self.lock, _source_publication_guard(result):
            if not self._can_publish(token, session, request_revision):
                return _json(409, {"error": "Conversation changed while the result was being prepared. Submit again."})
            _check_source_binding(result)
            current_run().finish()  # Publication linearizes here, before any state mutation.
            self.results[run_id] = payload
            self.result_owners[run_id] = token
            while len(self.results) > 16:
                expired, _ = self.results.popitem(last=False)
                self.result_owners.pop(expired, None)
        return response


    def _chat_request(self, body, token, session):
        owner = None
        state = session.chat
        try:
            try:
                request = json.loads(body.decode('utf-8'))
            except (ValueError, UnicodeError):
                raise ChatError('chat_invalid_request') from None
            message = self.chat_backend.validate(request)
            selection = (request['provider'], request['model'], request['web_search'])
            with self.lock:
                if self.sessions.get(token) is not session or time.monotonic()-session.last_seen > SESSION_TTL_SECONDS:
                    raise ChatError('chat_stale', status=409)
                if state.pending is not None:
                    raise ChatError('chat_busy', status=429)
                if request['revision'] != state.revision:
                    raise ChatError('chat_stale', status=409)
                if state.turns >= MAX_TURNS:
                    raise ChatError('chat_turn_limit', status=409)
                if state.selection is not None and state.selection != selection:
                    raise ChatError('chat_reset_required', status=409)
                now = time.monotonic()
                self.chat_backend.reserve_rates(state.attempts, now)
                owner = state.pending = object()
                revision = state.revision
                turns = state.turns
                history = state.messages
                display = state.display
            context = self.chat_backend.context(history, message, request['web_search'])
            checkpoint('chat_provider')
            answer = self.chat_backend.generate(request, context)
            reply = {**answer, 'role': 'assistant',
                     'ai_generated': answer.get('response_origin', 'model') == 'model', 'municipal_verified': False}
            response = _json(200, {'reply': reply, 'revision': revision+1, 'turns': turns+1,
                                   'provider': request['provider'] + ':' + request['model'],
                                   'context_turns': (len(json.loads(context)['messages'])-1)//2,
                                   'web_search_requested': request['web_search']})
            messages = json.loads(context)['messages'] + [{'role': 'assistant', 'content': answer['text']}]
            retained = max(0, len(messages)-2)
            display = tuple(display[-retained:]) if retained else ()
            new_display = display + ({'role': 'user', 'text': message}, reply)
            with self.lock, _source_publication_guard(answer):
                if (self.sessions.get(token) is not session or time.monotonic()-session.last_seen > SESSION_TTL_SECONDS
                        or state.revision != revision or state.pending is not owner):
                    raise ChatError('chat_stale', status=409)
                current_run().checkpoint('chat_publication')
                current_run().finish()
                state.messages = tuple(messages)
                state.display = new_display
                state.selection = selection
                state.revision += 1
                state.turns += 1
            return response
        except ChatError as error:
            return _chat_failure(error)
        except (OllamaError, OpenAIProviderError, RunStopped, ResearchError) as error:
            return _provider_failure(error)
        except Exception:
            return _json(422, {'error': 'Chatten kunne ikke fullføres. Ingen nytt svar ble lagret.',
                               'error_code': 'chat_failed', 'retryable': True})
        finally:
            if owner is not None:
                with self.lock:
                    if state.pending is owner:
                        state.pending = None


    def _portal_request(self, path: str, body: bytes, token: str, session: ClientSession) -> Response:
        from .search import InvalidQueryError, QueryPrivacyError, UnsupportedTopicError, validate_query
        from .categories import CATEGORY_IDS
        selected_created = False
        with self.lock:
            request_revision = session.revision
            prior_terms = session.topic_terms if session.turns < MAX_CONVERSATION_TURNS else ()
            prior_municipality = session.municipality_id if prior_terms else None
        try:
            request = json.loads(body.decode("utf-8"))
            allowed = {"query", "category"} if path == "/api/search" else {"query", "category", "provider", "model"}
            if not isinstance(request, dict) or set(request) - allowed or "query" not in request:
                raise ValueError("Invalid search request")
            query, category = request["query"], request.get("category")
            try:
                validate_query(query, real_sources=True, allow_followup=bool(prior_terms))
            except UnsupportedTopicError:
                # Safe but unrecognized topics get a clarification/empty result;
                # they are never forwarded to the model or retained.
                pass
            if category is not None and (not isinstance(category, str) or category not in CATEGORY_IDS):
                raise ValueError("Invalid category")
            selected_workflow = self.service
            if path == "/api/answer" and ("provider" in request or "model" in request):
                if not {"provider", "model"}.issubset(request):
                    raise ProviderSelectionError("Provider selection is incomplete")
                if self.provider_registry is None and self.service_factory is None:
                    choice = self._configured_service_choice()
                    if not choice["available"] or (request["provider"], request["model"]) != (choice["provider"], choice["model"]):
                        raise ProviderSelectionError("Only the configured service may be selected")
                else:
                    if self.provider_registry is None or self.service_factory is None:
                        raise ProviderSelectionError("Provider selection is unavailable")
                    self.provider_registry.require_choice(request["provider"], request["model"])
                    try:
                        selected_workflow = self.service_factory(request["provider"], request["model"])
                    except ValueError:
                        return _provider_failure(OllamaError("Provider startup configuration unavailable"), status=503)
                    selected_created = True
        except QueryPrivacyError:
            return _json(400, {"error": "Foresp\u00f8rselen ble avvist av hensyn til personvernet. Ikke skriv personopplysninger."})
        except ProviderSelectionError as error:
            return _provider_failure(error, status=400)
        except (InvalidQueryError, ValueError, UnicodeError, TypeError):
            return _json(400, {"error": "Ugyldig s\u00f8k. Bruk korte temaord uten personopplysninger eller nettadresser."})
        except (OSError, RuntimeError, KeyError) as error:
            return _provider_failure(error, status=503)
        try:
            if path == "/api/search":
                search=self.portal.search(query,category=category)
                with self.lock, _source_publication_guard(search):
                    if not self._can_publish(token,session,request_revision):
                        return _json(409,{'error':'Søket er endret. Prøv igjen.'})
                    _check_source_binding(search)
                    return _json(200,search)
            answer = self.portal.answer(query, category=category, workflow_service=selected_workflow,
                                        prior_terms=prior_terms,prior_municipality=prior_municipality)
        except SourceRefreshError:
            raise
        except (OllamaError, OpenAIProviderError, RealSourceError) as error:
            return _provider_failure(error)
        except (OSError, RuntimeError, ValueError, TypeError, KeyError) as error:
            return _provider_failure(error)
        finally:
            if selected_created:
                try:
                    closer = getattr(selected_workflow, "close", None)
                    if not callable(closer):
                        closer = getattr(getattr(selected_workflow, "summarizer", None), "client", None)
                        closer = getattr(closer, "close", None)
                    if callable(closer):
                        adapter = getattr(selected_workflow, 'adapter', None) or getattr(selected_workflow, 'summarizer', None)
                        cleanup_provider(getattr(adapter, 'client', None), closer)
                except Exception:
                    # Even SDK lookup/cleanup failures must not leak diagnostics.
                    # BaseException (including user interruption) still propagates.
                    pass
        try:
            policy=getattr(selected_workflow,'request_sources',None)
            query_terms=policy.search_query(query) if callable(getattr(policy,'search_query',None)) else query
            current_terms = (policy.context_terms(query) if callable(getattr(policy,'context_terms',None)) else
                validate_query(query_terms, real_sources=True, allow_followup=bool(prior_terms)))
        except ValueError:
            current_terms = []
        effective_terms = tuple(current_terms or prior_terms)
        answer["is_follow_up"] = bool(answer.get("is_follow_up", False))
        payload = json.dumps(answer, ensure_ascii=False).encode("utf-8")
        run_id = secrets.token_hex(16)
        response = _json(200, {"run_id": run_id, "answer": answer})
        with self.lock, _source_publication_guard(answer):
            if not self._can_publish(token, session, request_revision):
                return _json(409, {"error": "Conversation changed while the answer was being prepared. Submit the question again."})
            _check_source_binding(answer)
            current_run().finish()  # Deadline crossing must not leave a stored result/context.
            if answer.get("answer_status") in {"evidence_checked", "demo"} and answer.get("result"):
                session.topic_terms = effective_terms[:16]
                session.municipality_id=answer.get('municipality_id')
                session.turns = (session.turns + 1) if prior_terms else 1
            else:
                session.topic_terms = ()
                session.municipality_id=None
                session.turns = 0
            self.results[run_id] = payload
            self.result_owners[run_id] = token
            while len(self.results) > 16:
                expired, _ = self.results.popitem(last=False)
                self.result_owners.pop(expired, None)
        return response


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
                  provider_registry: ProviderRegistry | None = None, chat_backend=None) -> ThreadingHTTPServer:
    if getattr(service,'historical_baseline',False) or getattr(getattr(portal,'workflow',None),'historical_baseline',False):
        raise ValueError('Historical evaluation cannot be exposed by the production HTTP server')
    if service_factory is not None:
        factory=service_factory
        def production_factory(provider,model):
            workflow=factory(provider,model)
            if getattr(workflow,'historical_baseline',False):
                closer=getattr(workflow,'close',None)
                if callable(closer):
                    cleanup_provider(getattr(getattr(workflow,'adapter',None),'client',None),closer)
                raise ValueError('Historical evaluation is unavailable in production')
            return workflow
        service_factory=production_factory
    app = WebApplication(service, port=port, portal=portal, service_factory=service_factory,
                         provider_registry=provider_registry, chat_backend=chat_backend)
    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(app))
    app.port = server.server_port
    return server


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--catalog", type=Path, action="append", default=[], help="Offline reviewed catalog; repeat for multiple files")
    parser.add_argument("--approvals", type=Path, help="Individually reviewed page manifest; never enables live fetching")
    parser.add_argument("--research-policy", type=Path,
                        help="Reviewed Innlandet identities and exact source policy; never enables network access")
    parser.add_argument("--enable-live-research", action="store_true",
                        help="Explicit owner-authorized bounded official HTML research; no cloud source consent")
    parser.add_argument("--enable-local-router", action="store_true",
                        help="Opt in to one budgeted local Ollama classification helper; never grants source permissions")
    parser.add_argument("--router-model", default="llama3.2:3b", help="Already installed local classification model; no downloads")
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
        from .question_router import QuestionRouter,LocalSemanticClassifier
        question_router=QuestionRouter(LocalSemanticClassifier(args.router_model)) if args.enable_local_router else QuestionRouter()
        research = None
        if args.research_policy or args.enable_live_research:
            if not real_mode:
                raise ValueError("Regional source policy cannot use synthetic/demo mode")
            if args.enable_live_research:
                from .live_research import LiveResearchService
                research=LiveResearchService.from_reviewed_policy(
                    args.research_policy or Path('docs/innlandet-research.json'),enabled=True)
            else:
                from .research import ResearchService
                research = ResearchService.from_reviewed_policy(args.research_policy)
        if real_mode:
            selected_provider = args.provider or "ollama"
            if args.fallback_to_mock or selected_provider == "mock":
                raise ValueError("Real-source mode refuses mock fallback")
            catalog_paths = args.catalog or [Path("output/municipal-catalog.json")]
            approval_path = args.approvals or Path("docs/approved-service-pages.json")
            from .real_sources import create_municipal_service
            service = create_municipal_service(catalog_paths, approval_path, model=args.model,
                timeout=args.ollama_timeout, provider=selected_provider, request_sources=research)
            service_factory = lambda selected, model: create_municipal_service(
                catalog_paths, approval_path, model=model, timeout=args.ollama_timeout, provider=selected,
                request_sources=research)
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
                           service_factory=service_factory, provider_registry=provider_registry,
                           chat_backend=ChatBackend(research_service=research,
                               web_authorized=True if args.enable_live_research else None,question_router=question_router)) as server:
            print(f"Hamar KommuneAgent: http://127.0.0.1:{server.server_port} (provider: {service.provider})", flush=True)
            server.serve_forever()
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
