FROM python:3.12-slim

RUN groupadd -r appuser && useradd -r -g appuser -m appuser

WORKDIR /app

COPY pyproject.toml .
COPY src/ src/

RUN pip install --no-cache-dir .

RUN mkdir -p /app/data && chown -R appuser:appuser /app/data

USER appuser

EXPOSE 7863

CMD ["python", "-m", "cgc_claude_usage"]
