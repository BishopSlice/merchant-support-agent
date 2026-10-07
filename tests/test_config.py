from merchant_agent.config import get_settings


def test_settings_read_model_name_from_env(monkeypatch):
    monkeypatch.setenv("MODEL_NAME", "test-model")
    assert get_settings().model_name == "test-model"


def test_stores_dir_is_under_data_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    assert get_settings().stores_dir == tmp_path / "stores"
