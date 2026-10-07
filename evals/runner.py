"""Run one eval case against the agent, isolated on a throwaway copy of the data."""

import json
import os
import shutil
import tempfile
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path

import httpx
from google.adk import Runner
from google.genai.errors import APIError

from evals.case_format import EVAL_STORES_DIR, EvalCase
from evals.records import CaseRun, TokenUsage, ToolCallRecord, TurnRecord
from merchant_agent.chat import Usage, new_runner, new_session, run_turn
from merchant_agent.config import PROJECT_ROOT, ModelPrice, cost_usd
from merchant_agent.demo import apply_fix
from merchant_agent.tools.handoff import list_cases


@contextmanager
def isolated_workspace() -> Iterator[Path]:
    """Point the app at a fresh copy of data/ plus the eval stores, then put settings back."""
    saved = {key: os.environ.get(key) for key in ("DATA_DIR", "RUNTIME_DIR")}
    with tempfile.TemporaryDirectory(prefix="eval-") as tmp:
        data_dir = Path(tmp) / "data"
        shutil.copytree(PROJECT_ROOT / "data", data_dir)
        shutil.copytree(EVAL_STORES_DIR, data_dir / "stores", dirs_exist_ok=True)
        os.environ["DATA_DIR"] = str(data_dir)
        os.environ["RUNTIME_DIR"] = str(Path(tmp) / "runtime")
        try:
            yield data_dir
        finally:
            for key, value in saved.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value


async def run_case(
    case: EvalCase, price: ModelPrice, runner_factory: Callable[[], Runner] = new_runner
) -> CaseRun:
    """Play a case's scripted turns against the agent and record everything that happened."""
    record = CaseRun(case_id=case.id, category=case.category.value)
    total = Usage()
    started = time.monotonic()
    with isolated_workspace():
        runner = runner_factory()
        try:
            session_id = await new_session(runner, case.store)
            for scripted in case.turns:
                turn_record = TurnRecord(merchant=scripted.merchant)
                if scripted.fix:
                    turn_record.fix = scripted.fix.value
                    turn_record.fixed_product_ids = apply_fix(case.store, scripted.fix)
                record.turns.append(turn_record)
                turn = await run_turn(runner, session_id, scripted.merchant)
                turn_record.reply = turn.reply
                turn_record.tool_calls = [
                    ToolCallRecord(name=c.name, args=c.args, response=c.response)
                    for c in turn.tool_calls
                ]
                turn_record.usage = TokenUsage(**asdict(turn.usage))
                total += turn.usage
        except (APIError, httpx.HTTPError) as error:  # model or network errors: resume reruns these
            record.status, record.error = "error", f"{type(error).__name__}: {error}"
        finally:
            await runner.close()
        # Oldest first, so the last entry is the most recent handoff.
        record.handoff_cases = [json.loads(c.model_dump_json()) for c in reversed(list_cases())]
    record.usage = TokenUsage(**asdict(total))
    record.cost_usd = cost_usd(total, price)
    record.seconds = round(time.monotonic() - started, 1)
    return record
