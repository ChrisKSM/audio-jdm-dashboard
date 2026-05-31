FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml hml.py main.py README.md ./
COPY wRE_dashboard ./wRE_dashboard

RUN pip install --no-cache-dir \
    fastapi uvicorn[standard] jira python-dotenv httpx openai requests pydantic

EXPOSE 8200

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8200"]
