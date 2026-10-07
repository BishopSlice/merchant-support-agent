# How we write code here

These rules keep the project easy to grow, easy to test, and easy to explain in an interview.

1. **Tools are plain Python first.** Every tool in `src/merchant_agent/tools/` is a normal function that works and is tested without any AI model. The agent only decides *which* tool to call.
2. **One job per file.** A tool file does one thing. Shared data shapes live in `models.py`, settings in `config.py`.
3. **Typed and documented.** Every public function has type hints and a one line docstring that says what it does in plain words. The model reads tool docstrings, so they matter.
4. **No secrets in code.** Keys go in `.env` (never committed). `.env.example` shows what's needed.
5. **Data is separate from logic.** Feeds, help docs and eval cases are files in `data/` and `evals/`, not hardcoded in Python.
6. **Every behavior change gets measured.** If you change a prompt or tool, rerun the evals and save the result in `evals/results/`.
7. **Big choices get a decision record.** A short note in `docs/decisions/` saying what we chose, what we didn't, and why.
8. **Small commits with clear messages.** One idea per commit, written so a reviewer understands it without reading the code.
