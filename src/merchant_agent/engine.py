"""One conversation with the agent: one model call per answer where code can load the context,
and the tool loop as a recorded fallback (ADR 0008). Used by the web app, the evals and the CLI.
"""

import asyncio
import time
from collections.abc import Callable
from typing import Any

from merchant_agent.answer import AnswerFn, answer_turn, gemini_answer
from merchant_agent.chat import Turn, new_runner, new_session, run_turn
from merchant_agent.config import get_settings
from merchant_agent.preload import preload

DEFAULT = object()  # use Gemini for the one-call path


class Conversation:
    """A merchant's conversation about one store.

    entry_context is {product_name, issue_code} when the side panel was opened from an issue
    row. answer is the one-call model function; None turns the one-call path off, so every turn
    uses the tool loop (tests with a fake runner, and the old behaviour for comparison).
    """

    def __init__(
        self,
        store_id: str,
        entry_context: dict | None = None,
        runner_factory: Callable[[], Any] | None = None,
        answer: AnswerFn | None | object = DEFAULT,
    ) -> None:
        self.store_id = store_id
        self.entry_context = entry_context
        self.runner_factory = runner_factory or (lambda: new_runner())  # looked up when used
        self.answer = gemini_answer(get_settings().model_name) if answer is DEFAULT else answer
        self.history: list[tuple[str, str]] = []
        self.one_call_started = False
        self.runner = None
        self.session_id: str | None = None
        self.loop_turns = 0  # turns the tool loop's own session has seen

    async def ask(self, message: str) -> Turn:
        started = time.monotonic()
        if self.answer is not None:
            # In a worker thread, so a web server keeps serving others meanwhile.
            loaded = await asyncio.to_thread(preload, self.store_id, message, self.entry_context)
            # Follow-ups in a conversation already on the one-call path stay on it.
            if loaded.resolved or self.one_call_started:
                turn = await asyncio.to_thread(
                    answer_turn, self.store_id, list(self.history), message, loaded, self.answer
                )
                self.one_call_started = True
                return self._finish(message, turn, started)
        turn = await self._tool_loop(message)
        turn.path = "fallback" if self.answer is not None else "tool_loop"
        return self._finish(message, turn, started)

    async def _tool_loop(self, message: str) -> Turn:
        if self.runner is None:
            self.runner = self.runner_factory()
            extra = {"entry_context": self.entry_context} if self.entry_context else {}
            self.session_id = await new_session(self.runner, self.store_id, extra)
        # Turns answered on the one-call path aren't in the loop's own session: pass them on.
        missed = self.history[self.loop_turns :]
        text = message
        if missed:
            earlier = "\n".join(f"Merchant: {m}\nYou: {r}" for m, r in missed)
            text = f"(Earlier in this conversation:\n{earlier})\n\n{message}"
        self.loop_turns = len(self.history) + 1
        return await run_turn(self.runner, self.session_id, text)

    def _finish(self, message: str, turn: Turn, started: float) -> Turn:
        turn.seconds = round(time.monotonic() - started, 2)  # includes the preload
        self.history.append((message, turn.reply))
        return turn

    async def close(self) -> None:
        if self.runner is not None:
            await self.runner.close()
