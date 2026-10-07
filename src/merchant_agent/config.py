"""Settings loaded from the environment and .env file."""

import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseModel):
    """Where data lives and which model the agent uses."""

    model_name: str
    data_dir: Path
    runtime_dir: Path

    @property
    def stores_dir(self) -> Path:
        """Folder holding one subfolder per simulated store."""
        return self.data_dir / "stores"


def get_settings() -> Settings:
    """Load settings from .env (if present) and environment variables."""
    load_dotenv(PROJECT_ROOT / ".env")
    return Settings(
        model_name=os.getenv("MODEL_NAME", "gemini-3.6-flash"),
        data_dir=Path(os.getenv("DATA_DIR", PROJECT_ROOT / "data")),
        runtime_dir=Path(os.getenv("RUNTIME_DIR", PROJECT_ROOT / "runtime")),
    )
