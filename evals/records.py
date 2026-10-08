"""What an eval run records for each case: every turn, tool call, created case and token count."""

from pydantic import BaseModel, Field


class ToolCallRecord(BaseModel):
    """One tool the agent called, with its arguments and result."""

    name: str
    args: dict
    response: dict | list | str | None = None
    by: str = "model"  # "code" when code made the call itself (ADR 0008)


class TokenUsage(BaseModel):
    """Token counts for a turn or a whole case."""

    model_calls: int = 0
    input_tokens: int = 0
    cached_tokens: int = 0
    output_tokens: int = 0


class TurnRecord(BaseModel):
    """One merchant message and everything the agent did in reply."""

    merchant: str
    fix: str | None = None
    fixed_product_ids: list[str] = Field(default_factory=list)
    reply: str = ""
    tool_calls: list[ToolCallRecord] = Field(default_factory=list)
    usage: TokenUsage = Field(default_factory=TokenUsage)
    seconds: float = 0.0  # wall-clock time for the agent's reply
    path: str = "tool_loop"  # "one_call", "fallback" or "tool_loop" (ADR 0008)


class CaseRun(BaseModel):
    """The full record of running one eval case."""

    case_id: str
    category: str
    agent_version: str = ""  # merchant_agent.agent.agent_version() at run time
    status: str = "ok"  # "ok" or "error"
    error: str = ""
    turns: list[TurnRecord] = Field(default_factory=list)
    handoff_cases: list[dict] = Field(default_factory=list)
    usage: TokenUsage = Field(default_factory=TokenUsage)
    cost_usd: float = 0.0
    seconds: float = 0.0
