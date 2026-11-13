#!/usr/bin/env python3
"""
api.py -- Read-only FAQ search endpoint for DCR dynamic (REST) effects.

One call does everything the chatbot needs from retrieval: it embeds the
user's message, scores it against the FAQ vectors, applies the same
thresholds as the app (openchat.Settings), and returns a FLAT JSON object so
a DCR effect can pick values out by simple key lookup.

    GET  /api/faq/search?q=<user message>
    POST /api/faq/search      {"q": "<user message>"}
    GET  /health              liveness only, no auth, reveals nothing

Response (every key is always present; unused ones are "" / 0):

    decision        single_match | clarify_match | no_match
    score           best record score (0-1), also set for no_match
    id              matched FAQ id, e.g. FAQ_16  (single_match only)
    question        matched canonical question   (single_match only)
    answer          the answer text itself       (single_match only)
    citation        source citation              (single_match only)
    option_count    number of options            (clarify_match only, 0-3)
    option1_id / option1_question / option1_answer / option1_citation / option1_score   (clarify_match)
    option2_*, option3_*
    cached          true when served from the in-process LRU
    latency_ms      server-side time for this request

Errors use real HTTP status codes (400 bad query, 401 bad key, 503 search
unavailable) so DCR's ContinueOnFail path fires.

Security / privacy:
- Binds to 127.0.0.1 by default; expose it through a tunnel, not 0.0.0.0.
- Requires an API key (env FAQ_API_KEY). It is accepted as an X-API-Key (or X-DCR-AuthToken)
  header, as `Authorization: Bearer <key>` (DCR's token authenticator), or as
  the user name or password of `Authorization: Basic` (DCR's basic
  authenticator). A `key` query parameter is accepted ONLY with
  --allow-query-key, because URLs end up in logs.
- A rejected request logs which credential sources were present and the
  names (never the values) of the query parameters, to debug integrations.
- The query text is never written to this service's logs.
- Query length is capped (MAX_QUERY_CHARS).

Run (from the repo root, in the dcr conda env):

    export FAQ_API_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
    python -m faq_search.api
    cloudflared tunnel --url http://127.0.0.1:8090     # in a second terminal
"""
from __future__ import annotations

import argparse
import base64
import binascii
import hmac
import logging
import os
import sys
import threading
import time
from collections import OrderedDict

from flask import Flask, jsonify, request

log = logging.getLogger("faq_search.api")

MAX_QUERY_CHARS = 500
MAX_OPTIONS = 3
CACHE_SIZE = 256
DEFAULT_PORT = 8090


def normalize_query(text: str) -> str:
    """Cache key: case-folded with collapsed whitespace."""
    return " ".join(text.casefold().split())


def decide(results, settings) -> str:
    """Same decision rule as FAQRetriever.rank_candidates, applied to record scores."""
    if not results:
        return "no_match"
    top = results[0].score
    second = results[1].score if len(results) > 1 else 0.0
    if top >= settings.single and (top - second) >= settings.margin:
        return "single_match"
    if top >= settings.minimum:
        return "clarify_match"
    return "no_match"


def build_payload(decision: str, results, settings) -> dict:
    """Flat, fixed-shape response body (without latency_ms / cached)."""
    payload = {
        "decision": decision,
        "score": round(float(results[0].score), 4) if results else 0.0,
        "id": "",
        "question": "",
        "answer": "",
        "citation": "",
        "option_count": 0,
    }
    for i in range(1, MAX_OPTIONS + 1):
        payload[f"option{i}_id"] = ""
        payload[f"option{i}_question"] = ""
        payload[f"option{i}_answer"] = ""
        payload[f"option{i}_citation"] = ""
        payload[f"option{i}_score"] = 0.0

    if decision == "single_match":
        top = results[0]
        payload["id"] = top.id
        payload["question"] = top.canonical_question
        payload["answer"] = top.answer_text
        payload["citation"] = top.citation
    elif decision == "clarify_match":
        options = results[: min(settings.maximum, MAX_OPTIONS)]
        payload["option_count"] = len(options)
        for i, res in enumerate(options, start=1):
            payload[f"option{i}_id"] = res.id
            payload[f"option{i}_question"] = res.canonical_question
            payload[f"option{i}_answer"] = res.answer_text
            payload[f"option{i}_citation"] = res.citation
            payload[f"option{i}_score"] = round(float(res.score), 4)
    return payload


def create_app(retriever=None, settings=None, api_key: str | None = None,
               allow_query_key: bool = False) -> Flask:
    """Build the Flask app. `retriever` and `settings` are injectable for tests."""
    app = Flask(__name__)
    app.json.ensure_ascii = False  # return real UTF-8 (æøå), not \\u escapes

    state = {"retriever": retriever, "settings": settings}
    cache: OrderedDict[str, dict] = OrderedDict()
    cache_lock = threading.Lock()
    search_lock = threading.Lock()  # one embedding at a time keeps memory flat

    def get_settings():
        if state["settings"] is None:
            from dcrai.llm.openchat import Settings
            state["settings"] = Settings.from_env()
        return state["settings"]

    def get_retriever():
        if state["retriever"] is None:
            from faq_search.retriever import get_retriever as _get
            state["retriever"] = _get()
        return state["retriever"]

    def supplied_credentials() -> dict[str, list[str]]:
        """Credential candidates by source. Values stay in memory; only source names are ever logged."""
        found: dict[str, list[str]] = {}
        header = request.headers.get("X-API-Key", "")
        if header:
            found["x-api-key"] = [header]
        dcr_header = request.headers.get("X-DCR-AuthToken", "")  # DCR HttpTokenAuthenticator default header
        if dcr_header:
            found["x-dcr-authtoken"] = [dcr_header]
        auth = request.headers.get("Authorization", "")
        scheme, _, value = auth.partition(" ")
        value = value.strip()
        if scheme.lower() == "bearer" and value:
            found["bearer"] = [value]
        elif scheme.lower() == "basic" and value:
            try:
                user, _, password = base64.b64decode(value, validate=True).decode("utf-8").partition(":")
                found["basic"] = [part for part in (password, user) if part]
            except (binascii.Error, UnicodeDecodeError, ValueError):
                found["basic"] = []
        elif auth:
            found["authorization-other"] = []
        if allow_query_key and request.args.get("key"):
            found["query-key"] = [request.args["key"]]
        return found

    def authorized() -> bool:
        if not api_key:
            return True
        # FAQ_API_EXTRA_KEYS (comma separated): further accepted values, e.g. the stored token DCR sends
        extras = [k.strip() for k in os.getenv("FAQ_API_EXTRA_KEYS", "").split(",") if k.strip()]
        expected_all = [k.encode("utf-8") for k in [api_key, *extras]]
        return any(hmac.compare_digest(candidate.encode("utf-8"), expected)
                   for candidates in supplied_credentials().values() for candidate in candidates
                   for expected in expected_all)

    def error(status: int, message: str):
        resp = jsonify({"error": message})
        resp.status_code = status
        resp.headers["Cache-Control"] = "no-store"
        return resp

    def extract_query():
        query = request.args.get("q")
        if query is None and request.method == "POST":
            data = request.get_json(silent=True)
            if isinstance(data, dict):
                query = data.get("q")
            if query is None:
                query = request.form.get("q")
        return query

    @app.get("/health")
    def health():
        return jsonify({"status": "ok"})

    @app.route("/api/faq/search", methods=["GET", "POST"])
    def search():
        started = time.perf_counter()
        if not authorized():
            creds = supplied_credentials()
            lengths = {src: sorted(len(c) for c in vals) for src, vals in sorted(creds.items())}
            log.warning("rejected 401 credential_sources=%s credential_lengths=%s expected_length=%d arg_names=%s",
                        sorted(creds) or "none", lengths or "none", len(api_key or ""), sorted(request.args))
            return error(401, "unauthorized")

        query = extract_query()
        if not isinstance(query, str) or not query.strip():
            log.warning("rejected 400 missing q method=%s arg_names=%s form_names=%s content_type=%s "
                        "body_bytes=%s header_names=%s",
                        request.method, sorted(request.args), sorted(request.form),
                        request.content_type or "none", request.content_length or 0,
                        sorted(name.lower() for name in request.headers.keys()))
            return error(400, "missing query parameter 'q'")
        query = query.strip()
        if len(query) > MAX_QUERY_CHARS:
            return error(400, f"query longer than {MAX_QUERY_CHARS} characters")

        key = normalize_query(query)
        with cache_lock:
            cached = cache.get(key)
            if cached is not None:
                cache.move_to_end(key)
        was_cached = cached is not None

        if cached is None:
            try:
                settings_ = get_settings()
                with search_lock:
                    results = get_retriever().retrieve(query, top_k=MAX_OPTIONS)
                cached = build_payload(decide(results, settings_), results, settings_)
            except Exception:
                # Never log the query text itself.
                log.error("search failed (query_chars=%d)", len(query))
                return error(503, "search unavailable")
            with cache_lock:
                cache[key] = cached
                while len(cache) > CACHE_SIZE:
                    cache.popitem(last=False)

        elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
        body = dict(cached)
        body["cached"] = was_cached
        body["latency_ms"] = elapsed_ms
        log.info("search decision=%s score=%.3f query_chars=%d cached=%s ms=%.1f",
                 body["decision"], body["score"], len(query), was_cached, elapsed_ms)
        resp = jsonify(body)
        resp.headers["Cache-Control"] = "no-store"
        return resp

    @app.errorhandler(404)
    def not_found(_):
        return error(404, "not found")

    @app.errorhandler(405)
    def method_not_allowed(_):
        return error(405, "method not allowed")

    return app


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Read-only FAQ search API for DCR effects.")
    parser.add_argument("--host", default="127.0.0.1",
                        help="bind address (default 127.0.0.1; use a tunnel to expose it)")
    parser.add_argument("--port", type=int,
                        default=int(os.getenv("FAQ_API_PORT", str(DEFAULT_PORT))))
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--allow-query-key", action="store_true",
                        help="also accept the API key as ?key=... (ends up in logs)")
    parser.add_argument("--no-auth", action="store_true",
                        help="run without an API key (local testing only)")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    api_key = os.getenv("FAQ_API_KEY", "").strip()
    if not api_key and not args.no_auth:
        print("FAQ_API_KEY is not set. Set it, or pass --no-auth for local testing only.",
              file=sys.stderr)
        return 2
    if args.no_auth:
        api_key = ""
        log.warning("Running WITHOUT authentication. Do not expose this through a tunnel.")
    if args.host not in ("127.0.0.1", "localhost", "::1"):
        log.warning("Binding to %s: the service is reachable from the network.", args.host)

    # Load the model before accepting traffic so the first DCR call is not slow.
    from faq_search.retriever import get_retriever
    started = time.perf_counter()
    retriever = get_retriever()
    retriever.retrieve("warm up", top_k=1)
    log.info("Model and vectors ready in %.1fs", time.perf_counter() - started)

    # Same thresholds as the chat app (FAQ_SINGLE_THRESHOLD etc.), validated at startup.
    from dcrai.llm.openchat import Settings
    settings = Settings.from_env()
    log.info("Thresholds: single>=%.2f margin>=%.2f minimum>=%.2f max_options=%d",
             settings.single, settings.margin, settings.minimum, settings.maximum)

    app = create_app(retriever=retriever, settings=settings, api_key=api_key,
                     allow_query_key=args.allow_query_key)

    from waitress import serve
    log.info("Listening on http://%s:%d (auth %s)", args.host, args.port,
             "on" if api_key else "OFF")
    serve(app, host=args.host, port=args.port, threads=args.threads)
    return 0


if __name__ == "__main__":
    sys.exit(main())
