from merchant_agent.cli import Transcript


def test_transcript_saves_messages_and_tool_calls(tmp_path):
    transcript = Transcript("sample-store", "test-model")
    transcript.add("Merchant", "What happened?")
    transcript.add_tool_call("check_feed", {}, {"products_with_issues": 18})
    transcript.add("Agent", "18 products have problems.")
    path = tmp_path / "out" / "t.md"
    transcript.save(path)

    text = path.read_text()
    assert "`sample-store`" in text and "`test-model`" in text
    assert "**Merchant:** What happened?" in text
    assert '"products_with_issues": 18' in text
    assert "**Agent:** 18 products have problems." in text


def test_chat_survives_an_api_error_and_keeps_going(monkeypatch, capsys):
    import asyncio

    from google.genai.errors import ClientError

    from merchant_agent import cli
    from merchant_agent.engine import Conversation

    def failing_answer(system, prompt):
        raise ClientError(429, {"error": {"message": "quota exhausted"}})

    messages = iter(["first question about my products", "and what about prices?", "quit"])
    monkeypatch.setattr(cli, "Conversation", lambda store: Conversation(store, answer=failing_answer))
    monkeypatch.setattr("builtins.input", lambda prompt: next(messages))

    asyncio.run(cli.chat("sample-store", None))

    output = capsys.readouterr().out
    assert output.count("The agent couldn't answer") == 2
    assert "quota exhausted" in output
