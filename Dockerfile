FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml ./
COPY backend ./backend
COPY runner ./runner
COPY benchmark ./benchmark
COPY judges ./judges
COPY tool_environment ./tool_environment
COPY scripts ./scripts
COPY alembic.ini ./

RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir -e .

ENV PYTHONPATH=/app:/app/backend

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
