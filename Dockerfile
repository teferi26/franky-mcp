# franky-mcp over streamable HTTP. Intended for local use: there is no authentication.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
COPY data ./data
RUN pip install . && useradd --create-home --uid 10001 franky

USER franky
EXPOSE 8000
# Bind to all interfaces inside the container; publish only to localhost on the host (see README).
CMD ["franky-mcp", "--http", "--host", "0.0.0.0", "--port", "8000"]
