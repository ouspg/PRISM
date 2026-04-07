FROM python:3.12-slim

RUN pip install uv

WORKDIR /app

COPY pyproject.toml ./
COPY uv.lock* ./
RUN uv sync --no-dev || true

COPY src/ src/
COPY config/ config/
COPY sql/ sql/

RUN uv sync --no-dev

ENV PYTHONPATH=/app

ENTRYPOINT ["uv", "run"]
CMD ["prism", "collect"]
