# Repository Agent Guidelines

- Use `uv` for Python commands, environments, dependency resolution, and test/type-check execution.
- All Python code must be typed. Add explicit annotations for functions, methods, and non-obvious values.
- Follow PEP 8 and the Google Python Style Guide's general structure: clear modules, absolute imports, useful docstrings for public APIs, simple control flow, and explicit errors.
- Use Ruff as the formatter and linter. Run `make format` before final checks; it runs `ruff format` and `ruff check --fix`.
- Run `uv run ruff format --check obrist datasets tests`, `uv run ruff check obrist datasets tests`, and `uv run --group dev mypy obrist datasets tests` before completing Python changes. `make check` runs these plus package checks.
- Keep `tempobench` read-only at runtime; generated files belong under `.generated/`.
- Keep Tempo benchmark definitions in `datasets/tempobench/spec.py`; generated Harbor task trees belong under `.generated/`.
- Keep reusable Tempo runtime assets under `datasets/tempobench/shared/`.
- Keep Harbor-specific compile code isolated under `obrist/backends/harbor/`.
- Obrist is a task compiler only; run, view, diff, publish, and result workflows should use Harbor directly after compile.
