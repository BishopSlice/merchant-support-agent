"""Settings loaded from the environment and .env file."""

import os
from pathlib import Path
from typing import TYPE_CHECKING

from dotenv import load_dotenv
from pydantic import BaseModel

if TYPE_CHECKING:
    from merchant_agent.chat import Usage

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

    @property
    def cases_dir(self) -> Path:
        """Folder where handoff cases are saved while the app runs."""
        return self.runtime_dir / "cases"


def get_settings() -> Settings:
    """Load settings from .env (if present) and environment variables."""
    load_dotenv(PROJECT_ROOT / ".env")
    return Settings(
        model_name=os.getenv("MODEL_NAME", "gemini-3.6-flash"),
        data_dir=Path(os.getenv("DATA_DIR", PROJECT_ROOT / "data")),
        runtime_dir=Path(os.getenv("RUNTIME_DIR", PROJECT_ROOT / "runtime")),
    )


class ModelPrice(BaseModel):
    """Paid-tier price of a model in US dollars per million tokens."""

    input_per_million: float
    cached_input_per_million: float
    output_per_million: float  # includes thinking tokens


# Source: https://ai.google.dev/gemini-api/docs/pricing (page "Last updated 2026-10-07 UTC",
# read 7 Oct 2026). Standard tier. These are the prices "through December 31, 2026"; Google
# doubles them from 1 January 2027, so update this table then.
MODEL_PRICES = {
    "gemini-3.6-flash": ModelPrice(
        input_per_million=0.75, cached_input_per_million=0.075, output_per_million=3.75
    ),
}


def cost_usd(usage: "Usage", price: ModelPrice) -> float:
    """Dollar cost of some token usage at a given price."""
    uncached = usage.input_tokens - usage.cached_tokens
    return (
        uncached * price.input_per_million
        + usage.cached_tokens * price.cached_input_per_million
        + usage.output_tokens * price.output_per_million
    ) / 1_000_000
