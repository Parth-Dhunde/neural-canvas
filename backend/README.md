# NeuralCanvas Backend

FastAPI backend for [NeuralCanvas](../README.md).

See the [repository README](../README.md) for installation, configuration, and API overview.

## Quick start

Use Python 3.10 (it must match the Python that Instant-NGP's `pyngp` bindings were built for).

```bash
python3.10 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

## Tests

```bash
pip install pytest
python -m pytest
```
