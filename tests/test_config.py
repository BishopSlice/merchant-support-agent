from merchant_agent.config import get_settings


def test_settings_read_model_name_from_env(monkeypatch):
    monkeypatch.setenv("MODEL_NAME", "test-model")
    assert get_settings().model_name == "test-model"


def test_stores_dir_is_under_data_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    assert get_settings().stores_dir == tmp_path / "stores"


def test_cost_uses_cached_input_price_for_cached_tokens():
    from merchant_agent.chat import Usage
    from merchant_agent.config import ModelPrice, cost_usd

    price = ModelPrice(input_per_million=1.0, cached_input_per_million=0.1, output_per_million=4.0)
    usage = Usage(
        model_calls=1, input_tokens=1_000_000, cached_tokens=500_000, output_tokens=250_000
    )
    # 500k uncached at $1, 500k cached at $0.10, 250k output at $4
    assert cost_usd(usage, price) == 0.5 + 0.05 + 1.0


def test_default_model_has_a_published_price():
    from merchant_agent.config import MODEL_PRICES

    assert MODEL_PRICES["gemini-3.6-flash"].input_per_million == 0.75
    assert MODEL_PRICES["gemini-3.6-flash"].output_per_million == 3.75


def test_the_grader_model_is_set_separately_and_has_a_price(monkeypatch):
    from merchant_agent.config import MODEL_PRICES

    monkeypatch.setenv("MODEL_NAME", "gemini-3.5-flash-lite")
    monkeypatch.delenv("GRADER_MODEL", raising=False)
    settings = get_settings()
    assert settings.model_name == "gemini-3.5-flash-lite"
    assert settings.grader_model_name == "gemini-3.6-flash"  # scores stay comparable
    assert MODEL_PRICES["gemini-3.5-flash-lite"].input_per_million == 0.30
    assert MODEL_PRICES["gemini-3.5-flash-lite"].output_per_million == 2.50
