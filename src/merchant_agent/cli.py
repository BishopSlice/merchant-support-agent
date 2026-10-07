"""Chat with the agent in the terminal: uv run python -m merchant_agent.cli [--store ID]."""

import argparse
import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

from google.adk import Event, Runner
from google.adk.runners import InMemoryRunner
from google.genai import types

from merchant_agent.agent import build_agent
from merchant_agent.config import get_settings

APP_NAME = "merchant_support"
USER_ID = "merchant"


class Transcript:
    """Collects a conversation as markdown lines, including tool calls."""

    def __init__(self, store_id: str, model_name: str) -> None:
        started = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
        self.lines = [
            "# Transcript",
            "",
            f"- Store: `{store_id}`",
            f"- Model: `{model_name}`",
            f"- Started: {started}",
            "",
        ]

    def add(self, speaker: str, text: str) -> None:
        """Add one message to the transcript."""
        self.lines += [f"**{speaker}:** {text.strip()}", ""]

    def add_tool_call(self, name: str, args: dict, response: object) -> None:
        """Add a tool call and its full result as a collapsible block."""
        self.lines += [
            f"<details><summary>Tool call: <code>{name}({json.dumps(args)})</code></summary>",
            "",
            "```json",
            json.dumps(response, indent=2),
            "```",
            "",
            "</details>",
            "",
        ]

    def save(self, path: Path) -> None:
        """Write the transcript to a markdown file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(self.lines))


async def send(runner: Runner, session_id: str, text: str, transcript: Transcript) -> str:
    """Send one merchant message and return the agent's reply, logging tool calls."""
    message = types.Content(role="user", parts=[types.Part(text=text)])
    calls: dict[str, tuple[str, dict]] = {}
    reply = ""
    event: Event
    async for event in runner.run_async(
        user_id=USER_ID, session_id=session_id, new_message=message
    ):
        for part in (event.content.parts if event.content else None) or []:
            if part.function_call:
                call = part.function_call
                calls[call.id or call.name] = (call.name, dict(call.args or {}))
                print(f"  [calling {call.name}]")
            elif part.function_response:
                result = part.function_response
                name, args = calls.get(result.id or result.name, (result.name, {}))
                transcript.add_tool_call(name, args, result.response)
            elif part.text and not part.thought and event.is_final_response():
                reply += part.text
    return reply


async def chat(store_id: str, transcript_path: Path | None) -> None:
    """Run a chat loop until the merchant types 'quit' or input ends."""
    settings = get_settings()
    runner = InMemoryRunner(agent=build_agent(), app_name=APP_NAME)
    session = await runner.session_service.create_session(
        app_name=APP_NAME, user_id=USER_ID, state={"store_id": store_id}
    )
    transcript = Transcript(store_id, settings.model_name)
    print(f"Chatting as the owner of {store_id}. Type 'quit' to stop.\n")
    try:
        while True:
            try:
                text = input("you> ").strip()
            except EOFError:
                break
            if text.lower() in {"quit", "exit"}:
                break
            if not text:
                continue
            transcript.add("Merchant", text)
            reply = await send(runner, session.id, text, transcript)
            transcript.add("Agent", reply)
            print(f"\nagent> {reply}\n")
    finally:
        await runner.close()
        if transcript_path:
            transcript.save(transcript_path)
            print(f"Transcript saved to {transcript_path}")


def main() -> None:
    """Parse command line options and start the chat."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store", default="sample-store", help="store id under data/stores")
    parser.add_argument("--transcript", type=Path, help="save the conversation to this file")
    args = parser.parse_args()
    asyncio.run(chat(args.store, args.transcript))


if __name__ == "__main__":
    main()
