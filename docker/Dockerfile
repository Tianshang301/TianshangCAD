# Multi-stage build for the CAD MCP Server.
#
# Base deps (numpy + matplotlib + mcp) are already covered by the project
# ``dependencies``; the ``[render]`` optional extra is not required in the
# default image because matplotlib is a mandatory dependency.

# ---- Builder stage: compile + install to a user-local site-packages ----
FROM python:3.11-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src/ ./src/
RUN pip install --user --no-cache-dir -e .

# ---- Runtime stage: lean image ----
FROM python:3.11-slim AS runtime

ENV PATH=/root/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    CAD_RUNTIME=analytic \
    CAD_HEADLESS=true \
    CAD_TEMP_DIR=/tmp/tianshangcad \
    CAD_MAX_MEMORY=4096

COPY --from=builder /root/.local /root/.local
COPY --from=builder /app/src ./src/

RUN mkdir -p /app/data /app/config /tmp/tianshangcad

WORKDIR /app
EXPOSE 8081

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8081/health')" || exit 1

ENTRYPOINT ["python", "-m", "tianshangcad"]
CMD ["--transport", "http", "--port", "8081"]
