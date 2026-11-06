FROM python:3.12-slim
WORKDIR /code
COPY --from=ghcr.io/astral-sh/uv:0.12.23 /uv /usr/local/bin/uv
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
COPY backend ./backend
COPY data ./data
COPY knowledge ./knowledge
COPY scripts ./scripts
COPY alembic.ini ./
ENV PYTHONPATH=/code/backend:/code
RUN useradd --create-home opspilot
USER opspilot
CMD ["/code/.venv/bin/uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
