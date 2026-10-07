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
