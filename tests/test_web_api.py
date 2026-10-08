"""API tests for the web app (SPEC, Evals f): issues, product edits, chat, limits, replays,
cases and the specialist login. The model is never called: chat uses a fake runner."""

import json

import pytest
from fastapi.testclient import TestClient
from google.adk import Event
from google.adk.sessions import InMemorySessionService
from google.genai import types

from merchant_agent.tools import handoff
from merchant_agent.web.api import WebConfig, create_app

ACCESS = {"X-Access-Code": "let-me-in"}


class FakeRunner:
    """Replies "Re: <message>" and saves an appeal case when the message mentions an appeal."""

    def __init__(self) -> None:
        self.session_service = InMemorySessionService()

    async def run_async(self, *, user_id, session_id, new_message):
        session = await self.session_service.get_session(
            app_name="merchant_support", user_id=user_id, session_id=session_id
        )
        text = new_message.parts[0].text
        if "appeal" in text:
            args = {"reason": "policy_appeal", "merchant_request": "Appeal"}
            result = handoff.create_handoff_case(
                session.state["store_id"], "policy_appeal", [], [], "Appeal", "Review", []
            )
            call = types.FunctionCall(id="1", name="create_handoff_case", args=args)
            response = types.FunctionResponse(id="1", name="create_handoff_case", response=result)
            yield Event(
                author="agent",
                content=types.Content(role="model", parts=[types.Part(function_call=call)]),
            )
            yield Event(
                author="agent",
                content=types.Content(role="user", parts=[types.Part(function_response=response)]),
            )
        note = session.state.get("entry_note", "")
        yield Event(
            author="agent",
            content=types.Content(role="model", parts=[types.Part(text=f"Re: {text} | {note}")]),
        )

    async def close(self) -> None:
        pass


class ExplodingRunner(FakeRunner):
    """Fails the test if anything tries to talk to the model."""

    async def run_async(self, **kwargs):
        raise AssertionError("the model must not be called")
        yield  # pragma: no cover


@pytest.fixture
def env(monkeypatch, tmp_path):
    monkeypatch.setenv("RUNTIME_DIR", str(tmp_path / "runtime"))
    monkeypatch.delenv("DATA_DIR", raising=False)
    return tmp_path


def make_client(env, runner=FakeRunner, **overrides) -> TestClient:
    fields = {
        "access_code": "let-me-in",
        "specialist_code": "specialist-demo",
        "session_cap": 3,
        "daily_cap": 5,
        "replays_dir": env / "replays",
    }
    config = WebConfig(**(fields | overrides))
    return TestClient(create_app(config, runner_factory=runner))


@pytest.fixture
def client(env):
    with make_client(env) as c:
        yield c


def issues(client) -> dict:
    response = client.get("/api/issues")
    assert response.status_code == 200
    return response.json()


def product(client, offer_id: str) -> dict:
    return next(p for p in issues(client)["products"] if p["offerId"] == offer_id)


# --- issues ---


def test_issues_lists_products_with_their_issues_and_the_counts(client):
    data = issues(client)
    assert data["stats"]["disapprovedCount"] == "13"
    assert data["accountIssues"] == []
    flagged = {p["offerId"] for p in data["products"]}
    assert "HG-004" in flagged and "HG-001" not in flagged  # only products with issues
    codes = {i["code"] for i in product(client, "HG-004")["issues"]}
    assert codes == {"price_mismatch"}
    assert data["automation"]["price_updates"] is False
    assert product(client, "HG-004")["edit"]["price"] == "32.00 USD"  # feed format, for the form


# --- product edits ---


def test_editing_a_product_fixes_its_issue_for_this_session(client):
    assert client.post("/api/products/HG-004", json={"price": "36.00 USD"}).status_code == 200
    assert "HG-004" not in {p["offerId"] for p in issues(client)["products"]}


def test_edits_are_validated(client):
    assert client.post("/api/products/HG-004", json={"colour": "red"}).status_code == 422
    assert client.post("/api/products/HG-999", json={"price": "1.00 USD"}).status_code == 404
    response = client.post("/api/products/HG-004", json={"availability": "maybe"})
    assert response.status_code == 422


def test_sessions_are_isolated(env):
    # Two browser sessions on one app: separate cookies, so separate demo data and cases.
    with make_client(env) as a:
        b = TestClient(a.app)
        with b:
            a.post("/api/products/HG-004", json={"price": "36.00 USD"})
            assert "HG-004" not in {p["offerId"] for p in issues(a)["products"]}
            assert "HG-004" in {p["offerId"] for p in issues(b)["products"]}
            a.post("/api/chat", json={"message": "I want to appeal"}, headers=ACCESS)
            assert len(a.get("/api/session/cases").json()["cases"]) == 1
            assert b.get("/api/session/cases").json()["cases"] == []


def test_the_original_data_folder_is_never_edited(client):
    from merchant_agent.config import PROJECT_ROOT

    feed = PROJECT_ROOT / "data" / "stores" / "sample-store" / "feed.csv"
    before = feed.read_text()
    client.post("/api/products/HG-004", json={"price": "36.00 USD"})
    assert feed.read_text() == before


# --- chat, access code and caps ---


def test_chat_needs_the_access_code(client):
    assert client.post("/api/chat", json={"message": "hi"}).status_code == 401
    wrong = {"X-Access-Code": "nope"}
    assert client.post("/api/chat", json={"message": "hi"}, headers=wrong).status_code == 401


def test_chat_replies_with_steps_and_remaining_messages(client):
    data = client.post("/api/chat", json={"message": "hi"}, headers=ACCESS).json()
    assert data["reply"].startswith("Re: hi")
    assert data["remaining"] == 2
    assert data["steps"] == []


def test_chat_opened_from_an_issue_row_passes_the_entry_context(client):
    body = {
        "message": "how do I fix this?",
        "entry_context": {"offer_id": "HG-004", "issue_code": "price_mismatch"},
        "new_conversation": True,
    }
    reply = client.post("/api/chat", json=body, headers=ACCESS).json()["reply"]
    assert "en~US~HG-004" in reply and "price_mismatch" in reply


def test_a_handoff_returns_the_case_preview(client):
    data = client.post("/api/chat", json={"message": "I want to appeal"}, headers=ACCESS).json()
    [case] = client.get("/api/session/cases").json()["cases"]
    assert data["case"]["case_id"] == case["case_id"]
    assert data["case"]["preview"]["reason"] == "policy_appeal"
    assert any("case" in step.lower() for step in data["steps"])


def test_session_cap_returns_429_at_the_boundary_and_not_before(client):
    for _ in range(3):
        assert client.post("/api/chat", json={"message": "hi"}, headers=ACCESS).status_code == 200
    response = client.post("/api/chat", json={"message": "hi"}, headers=ACCESS)
    assert response.status_code == 429
    assert "limit" in response.json()["detail"].lower()


def test_daily_cap_applies_across_sessions(env):
    with make_client(env) as a:
        b = TestClient(a.app)
        with b:
            for _ in range(3):
                assert a.post("/api/chat", json={"message": "x"}, headers=ACCESS).status_code == 200
            for _ in range(2):
                assert b.post("/api/chat", json={"message": "x"}, headers=ACCESS).status_code == 200
            assert b.post("/api/chat", json={"message": "x"}, headers=ACCESS).status_code == 429


def test_live_chat_is_off_when_no_access_code_is_configured(env):
    with make_client(env, access_code=None) as c:
        assert c.post("/api/chat", json={"message": "hi"}, headers=ACCESS).status_code == 403


def test_empty_or_huge_messages_are_rejected(client):
    assert client.post("/api/chat", json={"message": "  "}, headers=ACCESS).status_code == 422
    big = {"message": "x" * 2001}
    assert client.post("/api/chat", json=big, headers=ACCESS).status_code == 422


# --- replays ---


def write_replay(env, replay_id="price-fix") -> None:
    folder = env / "replays"
    folder.mkdir(exist_ok=True)
    replay = {
        "id": replay_id,
        "title": "Fix a price",
        "agent_version": "abc",
        "turns": [{"merchant": "hi", "reply": "hello", "steps": []}],
    }
    (folder / f"{replay_id}.json").write_text(json.dumps(replay))


def test_replays_need_no_code_and_never_call_the_model(env):
    write_replay(env)
    with make_client(env, runner=ExplodingRunner) as c:
        listed = c.get("/api/replays").json()["replays"]
        assert [r["id"] for r in listed] == ["price-fix"]
        replay = c.get("/api/replays/price-fix").json()
        assert replay["turns"][0]["reply"] == "hello"
        assert c.get("/api/replays/../../.env").status_code == 404
        assert c.get("/api/replays/missing").status_code == 404


# --- specialist ---


def test_specialist_cases_need_the_demo_login(client):
    client.post("/api/chat", json={"message": "I want to appeal"}, headers=ACCESS)
    assert client.get("/api/cases").status_code == 401
    bad = client.post("/api/specialist/login", json={"code": "wrong"})
    assert bad.status_code == 401
    assert client.post("/api/specialist/login", json={"code": "specialist-demo"}).status_code == 200
    cases = client.get("/api/cases").json()["cases"]
    assert [c["reason"] for c in cases] == ["policy_appeal"]


# --- branding (SPEC, Evals f) ---


@pytest.mark.parametrize("path", ["/", "/specialist.html", "/app.js", "/specialist.js"])
def test_pages_carry_the_concept_label_and_no_google_branding(client, path):
    import re

    page = client.get(path)
    assert page.status_code == 200
    text = page.text
    assert "Merchant Center" not in text
    assert not re.search(r"<img[^>]+(google|logo)", text, re.IGNORECASE)
    assert not re.search(r"<svg[^>]*aria-label=\"[^\"]*google", text, re.IGNORECASE)
    if path.endswith(".html") or path == "/":
        assert "Concept prototype, not a Google product" in text


# --- event store (observability) ---


def test_live_turns_are_recorded_after_the_reply_with_source_and_entry_point(client, env):
    import sqlite3

    body = {
        "message": "hi from jo@example.com",
        "entry_context": {"offer_id": "HG-004", "issue_code": "price_mismatch"},
        "new_conversation": True,
    }
    data = client.post("/api/chat", json=body, headers=ACCESS).json()
    client.post("/api/chat", json={"message": "and again"}, headers=ACCESS)
    with sqlite3.connect(env / "runtime" / "events.sqlite") as db:
        conversations = db.execute("select source, entry_point from conversations").fetchall()
        turns = db.execute("select id, merchant from turns order by at").fetchall()
    assert conversations == [("live", "issue_row")]
    assert turns[0][0] == data["turn_id"]
    assert "[email]" in turns[0][1]
    assert len(turns) == 2


def test_replays_are_never_recorded(env):
    import sqlite3

    write_replay(env)
    with make_client(env, runner=ExplodingRunner) as c:
        c.get("/api/replays/price-fix")
    with sqlite3.connect(env / "runtime" / "events.sqlite") as db:
        assert db.execute("select count(*) from turns").fetchone() == (0,)


# --- feedback and sampled grading (Task 21c) ---


def test_feedback_is_stored_for_this_sessions_own_turns(env):
    import sqlite3

    with make_client(env) as a:
        b = TestClient(a.app)
        with b:
            turn_id = a.post("/api/chat", json={"message": "hi"}, headers=ACCESS).json()["turn_id"]
            assert a.post("/api/feedback", json={"turn_id": turn_id, "value": 1}).status_code == 200
            # Another session can't vote on this turn, and votes are 1 or -1.
            assert b.post("/api/feedback", json={"turn_id": turn_id, "value": -1}).status_code == 404
            assert a.post("/api/feedback", json={"turn_id": turn_id, "value": 3}).status_code == 422
    with sqlite3.connect(env / "runtime" / "events.sqlite") as db:
        assert db.execute("select turn_id, value from feedback").fetchall() == [(turn_id, 1)]


def fake_generate(calls):
    from evals.grader import CompletenessGrade, ReplyVerdict, WrongAdviceGrade
    from merchant_agent.chat import Usage

    def generate(prompt, schema):
        calls.append(schema.__name__)
        usage = Usage(model_calls=1, input_tokens=1000, output_tokens=100)
        if schema is WrongAdviceGrade:
            verdict = ReplyVerdict(turn=1, verdict="supported", evidence="ok")
            return WrongAdviceGrade(replies=[verdict]), usage
        return CompletenessGrade(verdict="complete", evidence="ok"), usage

    return generate


def grades(env):
    import sqlite3

    with sqlite3.connect(env / "runtime" / "events.sqlite") as db:
        return db.execute("select wrong_advice_rate, completeness from grades").fetchall()


def test_sampled_live_conversations_are_graded(env):
    calls = []
    with make_client(env, grade_sample_rate=1.0) as c:
        c.app.state.grade_generate = fake_generate(calls)
        c.post("/api/chat", json={"message": "I want to appeal"}, headers=ACCESS)
    assert calls == ["WrongAdviceGrade", "CompletenessGrade"]
    assert grades(env) == [(0.0, "complete")]


def test_grading_respects_the_sample_rate_and_the_daily_budget(env):
    calls = []
    with make_client(env, grade_sample_rate=0.0) as c:
        c.app.state.grade_generate = fake_generate(calls)
        c.post("/api/chat", json={"message": "hi"}, headers=ACCESS)
    with make_client(env, grade_sample_rate=1.0, grading_daily_budget_usd=0.0) as c:
        c.app.state.grade_generate = fake_generate(calls)
        c.post("/api/chat", json={"message": "hi"}, headers=ACCESS)
    assert calls == [] and grades(env) == []
