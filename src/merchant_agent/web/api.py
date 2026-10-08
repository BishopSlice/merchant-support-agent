"""The web app's API: the merchant shell, the agent side panel, replays and the specialist page.

Every browser session gets its own copy of the demo store (a store id like "s-1a2b3c..."),
so one visitor's edits and cases never show for another. The original data/ folder is copied
once at startup into runtime/web-data, and only that copy is ever written.
"""

import csv
import json
import os
import re
import secrets
import shutil
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any, Literal

import httpx
from fastapi import (
    BackgroundTasks,
    Cookie,
    Depends,
    FastAPI,
    Header,
    HTTPException,
    Request,
    Response,
)
from fastapi.staticfiles import StaticFiles
from google.genai.errors import APIError
from pydantic import BaseModel, ConfigDict, StringConstraints

from evals.records import TokenUsage, ToolCallRecord, TurnRecord
from merchant_agent import ops
from merchant_agent.agent import agent_version
from merchant_agent.chat import describe_tool_call
from merchant_agent.config import MODEL_PRICES, PROJECT_ROOT, cost_usd, get_settings
from merchant_agent.data import MockMerchantMcp
from merchant_agent.engine import DEFAULT, Conversation
from merchant_agent.events import EventStore, turn_checks
from merchant_agent.merchant_api import product_name
from merchant_agent.models import IssueType
from merchant_agent.stores import load_feed, load_store, store_dir
from merchant_agent.tools.handoff import list_cases
from merchant_agent.web.sampling import SampledGrader

SESSION_COOKIE = "sid"
SPECIALIST_COOKIE = "specialist"
OPS_COOKIE = "ops"
STATIC_DIR = Path(__file__).parent / "static"
_REPLAY_ID = re.compile(r"^[a-z0-9][a-z0-9-]*$")


class WebConfig(BaseModel):
    """Limits and codes for the hosted demo. Codes come from the environment, never the repo."""

    access_code: str | None = None  # None turns live chat off; replays still work
    specialist_code: str = "specialist-demo"  # a demo login, shown on the specialist page
    session_cap: int = 30
    daily_cap: int = 400
    max_sessions: int = 500  # oldest session copies are removed beyond this
    demo_store: str = "sample-store"
    replays_dir: Path = PROJECT_ROOT / "replays"
    secure_cookies: bool = False  # set true when served over HTTPS
    ops_code: str | None = None  # the /ops dashboard's own code; None turns /ops off
    grade_sample_rate: float = 0.1  # share of live conversations graded by the AI grader
    grading_daily_budget_usd: float = 0.50

    @classmethod
    def from_env(cls) -> "WebConfig":
        env = os.environ
        return cls(
            access_code=env.get("ACCESS_CODE") or None,
            specialist_code=env.get("SPECIALIST_CODE", "specialist-demo"),
            session_cap=int(env.get("SESSION_CAP", 30)),
            daily_cap=int(env.get("DAILY_CAP", 400)),
            secure_cookies=env.get("SECURE_COOKIES", "") == "1",
            ops_code=env.get("OPS_CODE") or None,
            grade_sample_rate=float(env.get("GRADE_SAMPLE_RATE", 0.1)),
            grading_daily_budget_usd=float(env.get("GRADING_DAILY_BUDGET_USD", 0.50)),
        )


# --- request bodies ---

Text = Annotated[str, StringConstraints(strip_whitespace=True)]


class ProductEdit(BaseModel):
    """The fields a merchant can change in the Edit product dialog. Omitted fields stay as is."""

    model_config = ConfigDict(extra="forbid")

    title: Annotated[Text, StringConstraints(min_length=1, max_length=300)] | None = None
    price: Annotated[Text, StringConstraints(pattern=r"^\d+(\.\d{1,2})? [A-Z]{3}$")] | None = None
    availability: Literal["in_stock", "out_of_stock", "preorder", "backorder"] | None = None
    image_link: Annotated[Text, StringConstraints(pattern=r"^(https?://\S+)?$")] | None = None
    gtin: Annotated[Text, StringConstraints(pattern=r"^(\d{8}|\d{12,14})?$")] | None = None
    shipping: (
        Annotated[
            Text, StringConstraints(pattern=r"^([A-Z]{2}:[^:]*:[^:]*:\d+(\.\d{1,2})? [A-Z]{3})?$")
        ]
        | None
    ) = None


class EntryContextIn(BaseModel):
    """The issue row the side panel was opened from."""

    offer_id: Annotated[str, StringConstraints(pattern=r"^[A-Z]{2}-\d{3}$")]
    issue_code: IssueType


class ChatIn(BaseModel):
    message: Annotated[Text, StringConstraints(min_length=1, max_length=2000)]
    entry_context: EntryContextIn | None = None
    new_conversation: bool = False


class LoginIn(BaseModel):
    code: str


class FeedbackIn(BaseModel):
    turn_id: str
    value: Literal[1, -1]


# --- sessions ---


@dataclass
class WebSession:
    """One browser session: its own store copy, message count and agent conversation."""

    store_id: str
    created: datetime
    messages: int = 0
    conversation: Conversation | None = None  # the open panel conversation
    event_conversation: str | None = None  # this conversation's id in the event store
    sampled: bool = False  # chosen for AI grading when the conversation started
    transcript: list[TurnRecord] = field(default_factory=list)  # this conversation, for grading
    turn_ids: set[str] = field(default_factory=set)  # turns this session may give feedback on


class Sessions:
    def __init__(self, config: WebConfig) -> None:
        self.config = config
        self.by_token: dict[str, WebSession] = {}
        self.daily: dict[str, int] = {}
        self.specialists: set[str] = set()
        self.operators: set[str] = set()

    def get_or_create(self, token: str | None) -> tuple[str, WebSession]:
        if token and token in self.by_token:
            return token, self.by_token[token]
        while len(self.by_token) >= self.config.max_sessions:
            oldest = min(self.by_token, key=lambda t: self.by_token[t].created)
            shutil.rmtree(store_dir(self.by_token.pop(oldest).store_id), ignore_errors=True)
        store_id = f"s-{secrets.token_hex(8)}"
        source = get_settings().stores_dir / self.config.demo_store
        shutil.copytree(source, get_settings().stores_dir / store_id)
        token = secrets.token_urlsafe(24)
        self.by_token[token] = WebSession(store_id=store_id, created=datetime.now(UTC))
        return token, self.by_token[token]

    def count_today(self) -> int:
        return self.daily.get(datetime.now(UTC).date().isoformat(), 0)

    def add_today(self) -> None:
        today = datetime.now(UTC).date().isoformat()
        self.daily = {today: self.daily.get(today, 0) + 1}


def _working_copy(config: WebConfig) -> None:
    """Copy the help docs and the demo store into runtime/web-data and point DATA_DIR at it."""
    settings = get_settings()
    work = settings.runtime_dir / "web-data"
    if work.resolve() != settings.data_dir.resolve():
        shutil.rmtree(work, ignore_errors=True)
        shutil.copytree(settings.data_dir / "help_docs", work / "help_docs")
        shutil.copytree(
            settings.stores_dir / config.demo_store, work / "stores" / config.demo_store
        )
    os.environ["DATA_DIR"] = str(work)


def _feed_path(store_id: str) -> Path:
    return store_dir(store_id) / "feed.csv"


def _issues_view(store_id: str) -> dict:
    """What the Needs attention page shows: counts, account issues, flagged products, settings."""
    mcp = MockMerchantMcp()
    products = mcp.call("list_products", account=store_id)["products"]
    [aggregate] = mcp.call("list_aggregate_product_statuses", account=store_id)[
        "aggregateProductStatuses"
    ]
    automation = load_store(store_id).automatic_improvements
    feed = {p.id: p for p in load_feed(store_id)}
    return {
        "stats": aggregate["stats"],
        "accountIssues": mcp.call("list_account_issues", account=store_id)["accountIssues"],
        "products": [
            {
                "offerId": p["offerId"],
                "name": p["name"],
                "title": p["productAttributes"].get("title", ""),
                "attributes": p["productAttributes"],
                "issues": p["productStatus"]["itemLevelIssues"],
                "edit": feed[p["offerId"]].model_dump(include=set(ProductEdit.model_fields)),
            }
            for p in products
            if p["productStatus"]["itemLevelIssues"]
        ],
        "automation": automation.model_dump() if automation else None,
    }


def create_app(
    config: WebConfig | None = None,
    runner_factory: Callable[[], Any] | None = None,
    answer: Any = DEFAULT,
) -> FastAPI:
    """Build the app. Tests pass a fake runner factory so the model is never called."""
    config = config or WebConfig.from_env()
    _working_copy(config)
    sessions = Sessions(config)
    events = EventStore(get_settings().runtime_dir / "events.sqlite")
    events.purge_old_text()
    grader = SampledGrader(events, config.grade_sample_rate, config.grading_daily_budget_usd)
    app = FastAPI(title="Merchant support agent (concept prototype)")
    app.state.grade_generate = None  # created on first use; tests set a fake

    def grade_generate():
        if app.state.grade_generate is None:
            from evals.grader import gemini_generate

            app.state.grade_generate = gemini_generate(get_settings().model_name)
        return app.state.grade_generate

    def session(response: Response, sid: Annotated[str | None, Cookie()] = None) -> WebSession:
        token, current = sessions.get_or_create(sid)
        if token != sid:
            response.set_cookie(
                SESSION_COOKIE, token, httponly=True, samesite="lax", secure=config.secure_cookies
            )
        return current

    Session = Annotated[WebSession, Depends(session)]

    @app.get("/api/issues")
    def issues(current: Session) -> dict:
        return _issues_view(current.store_id)

    @app.post("/api/products/{offer_id}")
    def edit_product(offer_id: str, edit: ProductEdit, current: Session) -> dict:
        path = _feed_path(current.store_id)
        with path.open(newline="") as f:
            reader = csv.DictReader(f)
            rows, columns = list(reader), reader.fieldnames or []
        row = next((r for r in rows if r["id"] == offer_id), None)
        if row is None:
            raise HTTPException(404, f"No product {offer_id}")
        row.update(edit.model_dump(exclude_none=True))
        with path.open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=columns, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
        return {"status": "saved", "offerId": offer_id}

    @app.post("/api/chat")
    async def chat(
        body: ChatIn,
        current: Session,
        background: BackgroundTasks,
        x_access_code: Annotated[str | None, Header()] = None,
    ) -> dict:
        if not config.access_code:
            raise HTTPException(403, "Live chat is off in this demo. Watch a replay instead.")
        if not secrets.compare_digest(x_access_code or "", config.access_code):
            raise HTTPException(401, "Live chat needs an access code.")
        if current.messages >= config.session_cap:
            raise HTTPException(
                429, f"You've reached this session's limit of {config.session_cap} messages."
            )
        if sessions.count_today() >= config.daily_cap:
            raise HTTPException(429, "The demo's daily message limit is used up. Try a replay.")
        current.messages += 1
        sessions.add_today()

        if body.new_conversation or current.conversation is None:
            entry = None
            if body.entry_context:
                entry = {
                    "product_name": product_name(current.store_id, body.entry_context.offer_id),
                    "issue_code": body.entry_context.issue_code.value,
                }
            if current.conversation is not None:
                await current.conversation.close()
            current.conversation = Conversation(
                current.store_id, entry, runner_factory=runner_factory, answer=answer
            )
            current.event_conversation = secrets.token_hex(16)
            current.sampled = grader.sample()
            current.transcript = []
            background.add_task(
                events.start_conversation,
                source="live",
                store_id=current.store_id,
                agent_version=agent_version(),
                model=get_settings().model_name,
                entry_point="issue_row" if body.entry_context else "help",
                conversation_id=current.event_conversation,
            )
        try:
            turn = await current.conversation.ask(body.message)
        except (APIError, httpx.HTTPError) as error:
            raise HTTPException(503, "The assistant is unavailable right now.") from error

        # Logged after the reply is sent, never during the merchant's wait.
        turn_id = secrets.token_hex(16)
        model = get_settings().model_name
        cost = cost_usd(turn.usage, MODEL_PRICES[model]) if model in MODEL_PRICES else 0.0
        current.turn_ids.add(turn_id)
        current.transcript.append(
            TurnRecord(
                merchant=body.message,
                reply=turn.reply,
                tool_calls=[
                    ToolCallRecord(name=c.name, args=c.args, response=c.response, by=c.by)
                    for c in turn.tool_calls
                ],
                usage=TokenUsage(**asdict(turn.usage)),
                seconds=turn.seconds,
                path=turn.path,
            )
        )
        background.add_task(
            events.record_turn,
            current.event_conversation,
            body.message,
            turn,
            cost,
            turn_id,
            turn_checks(current.transcript),
        )
        if current.sampled:
            background.add_task(
                grader.grade,
                current.event_conversation,
                list(current.transcript),
                grade_generate(),
                MODEL_PRICES.get(model),
            )
        created = [
            c.response
            for c in turn.tool_calls
            if c.name == "create_handoff_case"
            and isinstance(c.response, dict)
            and c.response.get("status") == "created"
        ]
        return {
            "reply": turn.reply,
            "steps": [describe_tool_call(c) for c in turn.tool_calls],
            "case": created[-1] if created else None,
            "remaining": config.session_cap - current.messages,
            "turn_id": turn_id,
            "seconds": turn.seconds,
            "path": turn.path,
        }

    @app.post("/api/feedback")
    def feedback(body: FeedbackIn, current: Session) -> dict:
        if body.turn_id not in current.turn_ids:
            raise HTTPException(404, "No such reply in this session.")
        try:
            events.record_feedback(body.turn_id, body.value)
        except KeyError as error:
            raise HTTPException(409, "That reply is still being saved. Try again.") from error
        return {"status": "saved"}

    @app.get("/api/session/cases")
    def my_cases(current: Session) -> dict:
        mine = [c for c in list_cases() if c.store_id == current.store_id]
        return {"cases": [json.loads(c.model_dump_json()) for c in mine]}

    @app.get("/api/replays")
    def replays() -> dict:
        folder = config.replays_dir
        files = sorted(folder.glob("*.json")) if folder.is_dir() else []
        listed = []
        for path in files:
            data = json.loads(path.read_text())
            listed.append({"id": path.stem, "title": data.get("title", path.stem)})
        return {"replays": listed}

    @app.get("/api/replays/{replay_id}")
    def replay(replay_id: str) -> dict:
        path = config.replays_dir / f"{replay_id}.json"
        if not _REPLAY_ID.match(replay_id) or not path.is_file():
            raise HTTPException(404, "No such replay")
        return json.loads(path.read_text())

    @app.post("/api/specialist/login")
    def specialist_login(body: LoginIn, response: Response) -> dict:
        if not secrets.compare_digest(body.code, config.specialist_code):
            raise HTTPException(401, "Wrong demo code.")
        token = secrets.token_urlsafe(24)
        sessions.specialists.add(token)
        response.set_cookie(
            SPECIALIST_COOKIE, token, httponly=True, samesite="lax", secure=config.secure_cookies
        )
        return {"status": "signed in"}

    @app.get("/api/cases")
    def all_cases(request: Request) -> dict:
        if request.cookies.get(SPECIALIST_COOKIE) not in sessions.specialists:
            raise HTTPException(401, "Sign in with the demo specialist code.")
        return {"cases": [json.loads(c.model_dump_json()) for c in list_cases()]}

    @app.post("/api/ops/login")
    def ops_login(body: LoginIn, response: Response) -> dict:
        if not config.ops_code:
            raise HTTPException(403, "The ops dashboard is off: no OPS_CODE is set.")
        if not secrets.compare_digest(body.code, config.ops_code):
            raise HTTPException(401, "Wrong ops code.")
        token = secrets.token_urlsafe(24)
        sessions.operators.add(token)
        response.set_cookie(
            OPS_COOKIE, token, httponly=True, samesite="lax", secure=config.secure_cookies
        )
        return {"status": "signed in"}

    def operator(request: Request) -> None:
        if request.cookies.get(OPS_COOKIE) not in sessions.operators:
            raise HTTPException(401, "Sign in with the ops code.")

    Source = Literal["live", "eval"]

    @app.get("/api/ops/summary", dependencies=[Depends(operator)])
    def ops_summary(source: Source = "live", days: int = 30) -> dict:
        return ops.summary(events, source=source, days=days)

    @app.get("/api/ops/conversations", dependencies=[Depends(operator)])
    def ops_conversations(source: Source = "live") -> dict:
        return {"conversations": ops.conversations(events, source=source)}

    @app.get("/api/ops/conversations/{conversation_id}", dependencies=[Depends(operator)])
    def ops_trace(conversation_id: str) -> dict:
        detail = ops.trace(events, conversation_id)
        if detail is None:
            raise HTTPException(404, "No such conversation.")
        return detail

    if STATIC_DIR.is_dir():
        app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
    return app


def __getattr__(name: str) -> FastAPI:
    """`uvicorn merchant_agent.web.api:app` builds the app on first access, from the env."""
    if name == "app":
        globals()["app"] = create_app()
        return globals()["app"]
    raise AttributeError(name)
