"""Chat with the agent in the terminal: uv run python -m merchant_agent.cli [--store ID]."""

import argparse
import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

from google.genai.errors import APIError

from merchant_agent.chat import describe_tool_call
from merchant_agent.config import get_settings
from merchant_agent.engine import Conversation


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


async def send(conversation: Conversation, text: str, transcript: Transcript) -> str:
    """Send one merchant message and return the agent's reply, logging tool calls."""
    turn = await conversation.ask(text)
    for call in turn.tool_calls:
        print(f"  [{describe_tool_call(call)}]")
        transcript.add_tool_call(call.name, call.args, call.response)
    return turn.reply


async def chat(store_id: str, transcript_path: Path | None) -> None:
    """Run a chat loop until the merchant types 'quit' or input ends."""
    settings = get_settings()
    conversation = Conversation(store_id)
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
            try:
                reply = await send(conversation, text, transcript)
            except APIError as error:  # e.g. rate limits: report it and let the merchant retry
                print(f"\nThe agent couldn't answer: {error}\n")
                continue
            transcript.add("Agent", reply)
            print(f"\nagent> {reply}\n")
    finally:
        await conversation.close()
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
