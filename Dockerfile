# The hosted demo: one container serving the API and the static front end (ADR 0006).
# Keys and codes (GOOGLE_API_KEY, ACCESS_CODE, OPS_CODE, SPECIALIST_CODE) come from the
# host's secret store at run time, never from this image.
FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:0.11.17 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src ./src
COPY data ./data
COPY replays ./replays
# The live grader reuses the eval rubrics and records.
COPY evals/__init__.py evals/grader.py evals/records.py ./evals/
COPY evals/rubrics ./evals/rubrics
RUN uv sync --frozen --no-dev

RUN useradd --create-home app && mkdir -p /tmp/runtime && chown app /tmp/runtime
USER app
ENV RUNTIME_DIR=/tmp/runtime SECURE_COOKIES=1 PORT=8080
EXPOSE 8080
CMD ["sh", "-c", "uv run --no-sync uvicorn merchant_agent.web.api:app --host 0.0.0.0 --port ${PORT}"]
