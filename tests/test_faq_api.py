"""Tests for the DCR-facing FAQ search API (faq_search/api.py).

These use a fake retriever, so they run without the embedding model.
"""
import os
import unittest
from types import SimpleNamespace
from unittest import mock

from faq_search.api import MAX_QUERY_CHARS, build_payload, create_app, decide

SETTINGS = SimpleNamespace(single=0.80, minimum=0.50, margin=0.12, maximum=3)
KEY = "test-key-123"


def result(rid, score, question=None, answer=None):
    return SimpleNamespace(
        id=rid,
        canonical_question=question or f"Question {rid}?",
        answer_text=answer or f"Answer {rid}.",
        citation=f"Citation {rid}",
        score=score,
    )


class FakeRetriever:
    def __init__(self, results=None, error=None):
        self.results = results or []
        self.error = error
        self.calls = []

    def retrieve(self, query, top_k=3):
        self.calls.append(query)
        if self.error:
            raise self.error
        return self.results[:top_k]


def make_client(results=None, error=None, api_key=KEY, allow_query_key=False):
    fake = FakeRetriever(results, error)
    app = create_app(retriever=fake, settings=SETTINGS, api_key=api_key,
                     allow_query_key=allow_query_key)
    return app.test_client(), fake


HEADERS = {"X-API-Key": KEY}


class TestDecision(unittest.TestCase):
    def test_single_match_needs_score_and_margin(self):
        self.assertEqual(decide([result("a", 0.90), result("b", 0.60)], SETTINGS), "single_match")

    def test_small_margin_is_clarify(self):
        self.assertEqual(decide([result("a", 0.90), result("b", 0.85)], SETTINGS), "clarify_match")

    def test_mid_score_is_clarify(self):
        self.assertEqual(decide([result("a", 0.65), result("b", 0.30)], SETTINGS), "clarify_match")

    def test_low_score_is_no_match(self):
        self.assertEqual(decide([result("a", 0.40)], SETTINGS), "no_match")

    def test_empty_is_no_match(self):
        self.assertEqual(decide([], SETTINGS), "no_match")

    def test_single_result_has_zero_runner_up(self):
        self.assertEqual(decide([result("a", 0.81)], SETTINGS), "single_match")


class TestPayloadShape(unittest.TestCase):
    EXPECTED_KEYS = {
        "decision", "score", "id", "question", "answer", "citation", "option_count",
        *(f"option{i}_{f}" for i in (1, 2, 3) for f in ("id", "question", "answer", "citation", "score")),
    }

    def test_all_keys_always_present(self):
        for decision, results in (
            ("single_match", [result("a", 0.95)]),
            ("clarify_match", [result("a", 0.6), result("b", 0.55)]),
            ("no_match", []),
        ):
            with self.subTest(decision=decision):
                self.assertEqual(set(build_payload(decision, results, SETTINGS)), self.EXPECTED_KEYS)

    def test_single_match_fills_answer_only(self):
        p = build_payload("single_match", [result("a", 0.95, answer="Full answer")], SETTINGS)
        self.assertEqual(p["answer"], "Full answer")
        self.assertEqual(p["id"], "a")
        self.assertEqual(p["option_count"], 0)
        self.assertEqual(p["option1_id"], "")
        self.assertEqual(p["option1_question"], "")

    def test_clarify_fills_options_with_answers(self):
        p = build_payload("clarify_match", [result("a", 0.7), result("b", 0.6), result("c", 0.55)], SETTINGS)
        self.assertEqual(p["option_count"], 3)
        self.assertEqual(p["option2_answer"], "Answer b.")
        self.assertEqual(p["option2_citation"], "Citation b")
        self.assertEqual([p["option1_id"], p["option2_id"], p["option3_id"]], ["a", "b", "c"])
        self.assertEqual(p["answer"], "")
        self.assertEqual(p["id"], "")

    def test_no_match_is_blank_but_keeps_score(self):
        p = build_payload("no_match", [result("a", 0.31)], SETTINGS)
        self.assertEqual(p["answer"], "")
        self.assertEqual(p["id"], "")
        self.assertEqual(p["score"], 0.31)


class TestEndpoint(unittest.TestCase):
    def test_get_single_match(self):
        client, _ = make_client([result("a", 0.93, answer="Yes, you can.")])
        r = client.get("/api/faq/search?q=can I work", headers=HEADERS)
        self.assertEqual(r.status_code, 200)
        body = r.get_json()
        self.assertEqual(body["decision"], "single_match")
        self.assertEqual(body["answer"], "Yes, you can.")
        self.assertFalse(body["cached"])
        self.assertIn("latency_ms", body)
        self.assertEqual(r.headers["Cache-Control"], "no-store")

    def test_post_json_and_form(self):
        client, _ = make_client([result("a", 0.93)])
        r1 = client.post("/api/faq/search", json={"q": "hello"}, headers=HEADERS)
        r2 = client.post("/api/faq/search", data={"q": "hello again"}, headers=HEADERS)
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r2.status_code, 200)

    def test_clarify_and_no_match_over_http(self):
        client, _ = make_client([result("a", 0.6), result("b", 0.55)])
        body = client.get("/api/faq/search?q=something", headers=HEADERS).get_json()
        self.assertEqual(body["decision"], "clarify_match")
        self.assertEqual(body["option_count"], 2)
        client, _ = make_client([result("a", 0.2)])
        body = client.get("/api/faq/search?q=weather", headers=HEADERS).get_json()
        self.assertEqual(body["decision"], "no_match")

    def test_bad_queries_are_400(self):
        client, fake = make_client([result("a", 0.9)])
        for label, resp in (
            ("missing", client.get("/api/faq/search", headers=HEADERS)),
            ("blank", client.get("/api/faq/search?q=%20%20", headers=HEADERS)),
            ("too long", client.get("/api/faq/search?q=" + "x" * (MAX_QUERY_CHARS + 1), headers=HEADERS)),
            ("not a string", client.post("/api/faq/search", json={"q": 5}, headers=HEADERS)),
        ):
            with self.subTest(label):
                self.assertEqual(resp.status_code, 400)
        self.assertEqual(fake.calls, [])

    def test_query_at_limit_is_accepted(self):
        client, _ = make_client([result("a", 0.9)])
        r = client.get("/api/faq/search?q=" + "x" * MAX_QUERY_CHARS, headers=HEADERS)
        self.assertEqual(r.status_code, 200)

    def test_danish_characters_round_trip_as_utf8(self):
        client, fake = make_client([result("a", 0.9, answer="Du kan få handicaptillæg ø å")])
        r = client.get("/api/faq/search", query_string={"q": "Kan jeg få handicaptillæg?"}, headers=HEADERS)
        self.assertEqual(fake.calls, ["Kan jeg få handicaptillæg?"])
        self.assertIn("handicaptillæg ø å".encode("utf-8"), r.data)
        self.assertNotIn(b"\\u00e6", r.data)

    def test_special_characters_in_query(self):
        client, fake = make_client([result("a", 0.9)])
        nasty = 'a "quoted" & b?x=1 #frag'
        r = client.get("/api/faq/search", query_string={"q": nasty}, headers=HEADERS)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(fake.calls, [nasty])

    def test_unknown_route_and_method_return_json(self):
        client, _ = make_client()
        self.assertEqual(client.get("/nope").get_json(), {"error": "not found"})
        r = client.put("/api/faq/search", headers=HEADERS)
        self.assertEqual(r.status_code, 405)
        self.assertEqual(r.get_json(), {"error": "method not allowed"})


class TestAuth(unittest.TestCase):
    def test_missing_or_wrong_key_is_401(self):
        client, fake = make_client([result("a", 0.9)])
        self.assertEqual(client.get("/api/faq/search?q=x").status_code, 401)
        self.assertEqual(client.get("/api/faq/search?q=x", headers={"X-API-Key": "wrong"}).status_code, 401)
        self.assertEqual(fake.calls, [])

    def test_dcr_token_header_accepted(self):
        client, _ = make_client([result("a", 0.9)])
        self.assertEqual(client.get("/api/faq/search?q=x", headers={"X-DCR-AuthToken": KEY}).status_code, 200)
        self.assertEqual(client.get("/api/faq/search?q=x", headers={"X-DCR-AuthToken": "wrong"}).status_code, 401)

    def test_extra_key_from_env_accepted(self):
        client, _ = make_client([result("a", 0.9)])
        with mock.patch.dict(os.environ, {"FAQ_API_EXTRA_KEYS": "portal-token, other"}):
            r = client.get("/api/faq/search?q=x", headers={"X-DCR-AuthToken": "portal-token"})
            self.assertEqual(r.status_code, 200)
            r = client.get("/api/faq/search?q=x", headers={"X-DCR-AuthToken": "nope"})
            self.assertEqual(r.status_code, 401)
        r = client.get("/api/faq/search?q=x", headers={"X-DCR-AuthToken": "portal-token"})
        self.assertEqual(r.status_code, 401)

    def test_query_param_key_rejected_by_default(self):
        client, _ = make_client([result("a", 0.9)])
        self.assertEqual(client.get(f"/api/faq/search?q=x&key={KEY}").status_code, 401)

    def test_query_param_key_allowed_when_enabled(self):
        client, _ = make_client([result("a", 0.9)], allow_query_key=True)
        self.assertEqual(client.get(f"/api/faq/search?q=x&key={KEY}").status_code, 200)

    def test_bearer_token_is_accepted(self):
        client, _ = make_client([result("a", 0.9)])
        ok = client.get("/api/faq/search?q=x", headers={"Authorization": f"Bearer {KEY}"})
        bad = client.get("/api/faq/search?q=x", headers={"Authorization": "Bearer nope"})
        self.assertEqual((ok.status_code, bad.status_code), (200, 401))

    def test_basic_auth_password_or_user_is_accepted(self):
        import base64
        client, _ = make_client([result("a", 0.9)])
        for label, pair in (("password", f"anyone:{KEY}"), ("user", f"{KEY}:"), ("wrong", "anyone:nope")):
            token = base64.b64encode(pair.encode()).decode()
            r = client.get("/api/faq/search?q=x", headers={"Authorization": f"Basic {token}"})
            with self.subTest(label):
                self.assertEqual(r.status_code, 401 if label == "wrong" else 200)

    def test_malformed_authorization_header_is_401_not_500(self):
        client, _ = make_client([result("a", 0.9)])
        for header in ("Basic !!!notbase64", "Bearer", "Digest abc", "Basic "):
            with self.subTest(header):
                r = client.get("/api/faq/search?q=x", headers={"Authorization": header})
                self.assertEqual(r.status_code, 401)

    def test_rejection_log_names_sources_but_never_values(self):
        client, _ = make_client([result("a", 0.9)])
        with self.assertLogs("faq_search.api", level="WARNING") as logs:
            client.get("/api/faq/search", query_string={"q": "private text"},
                       headers={"Authorization": "Bearer wrong-secret-value"})
            client.get("/api/faq/search", headers=HEADERS)  # no q: 400
        text = "\n".join(logs.output)
        self.assertIn("bearer", text)
        self.assertIn("arg_names=['q']", text)
        self.assertIn("arg_names=[]", text)
        self.assertIn("header_names=", text)
        self.assertNotIn("wrong-secret-value", text)
        self.assertNotIn("private text", text)

    def test_health_needs_no_key(self):
        client, _ = make_client()
        r = client.get("/health")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json(), {"status": "ok"})

    def test_no_api_key_configured_means_open(self):
        client, _ = make_client([result("a", 0.9)], api_key="")
        self.assertEqual(client.get("/api/faq/search?q=x").status_code, 200)


class TestCacheAndFailure(unittest.TestCase):
    def test_repeat_query_is_cached_across_case_and_whitespace(self):
        client, fake = make_client([result("a", 0.93)])
        first = client.get("/api/faq/search?q=Can  I work", headers=HEADERS).get_json()
        second = client.get("/api/faq/search?q=can i WORK", headers=HEADERS).get_json()
        self.assertFalse(first["cached"])
        self.assertTrue(second["cached"])
        self.assertEqual(len(fake.calls), 1)
        self.assertEqual(first["answer"], second["answer"])

    def test_retriever_failure_is_503_and_not_cached(self):
        client, fake = make_client(error=RuntimeError("model exploded"))
        with self.assertLogs("faq_search.api", level="ERROR"):
            r = client.get("/api/faq/search?q=secret medical details", headers=HEADERS)
            self.assertEqual(r.status_code, 503)
            self.assertEqual(r.get_json(), {"error": "search unavailable"})
            client.get("/api/faq/search?q=secret medical details", headers=HEADERS)
        self.assertEqual(len(fake.calls), 2)

    def test_query_text_is_never_logged(self):
        secret = "my diagnosis is very private"
        client, _ = make_client([result("a", 0.93)])
        with self.assertLogs("faq_search.api", level="INFO") as logs:
            client.get("/api/faq/search", query_string={"q": secret}, headers=HEADERS)
        self.assertTrue(logs.output)
        self.assertNotIn("diagnosis", "\n".join(logs.output))

        client, _ = make_client(error=RuntimeError("boom"))
        with self.assertLogs("faq_search.api", level="ERROR") as logs:
            client.get("/api/faq/search", query_string={"q": secret}, headers=HEADERS)
        self.assertNotIn("diagnosis", "\n".join(logs.output))


if __name__ == "__main__":
    unittest.main()
