FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY src ./src
COPY tests ./tests
COPY alembic.ini .
COPY migrations ./migrations
COPY .env.example .

# Pinned tokenizer asset required by the chunking adapter at runtime.
COPY assets/tokenizers/nomic-embed-text-v1.5/tokenizer.json ./assets/tokenizers/nomic-embed-text-v1.5/tokenizer.json

ENV PYTHONPATH=/app/src

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]