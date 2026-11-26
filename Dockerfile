# Stage 1: build the screen
FROM node:26-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

# Stage 2: the Python packages. A few (zstandard, pyyaml) have no ready-made wheel for this Python yet, so they
# are compiled here. The compiler stays in this stage; only the finished wheels reach the war room.
FROM python:3.15-slim AS wheels
# Use requirements-cloud.lock to include the Azure / Bedrock / Vertex libraries:
#   docker build --build-arg LOCKFILE=requirements-cloud.lock -t aegis-war-room .
ARG LOCKFILE=requirements.lock
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /build
COPY requirements.lock requirements-cloud.lock ./
# Every download is checked against the hash recorded in the lock file. A tampered package fails the build.
RUN pip wheel --no-cache-dir --require-hashes --wheel-dir /wheels -r ${LOCKFILE}

# Stage 3: the war room, with no compiler in it
FROM python:3.15-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 AEGIS_HOME=/app AEGIS_AUDIT_LOG=/data/audit.log.jsonl
WORKDIR /app
# The wheels were hash-checked in the stage above; they are mounted for this one step, not copied into a layer.
RUN --mount=type=bind,from=wheels,source=/wheels,target=/wheels \
    pip install --no-cache-dir --no-index --no-deps /wheels/*.whl
COPY pyproject.toml README.md ./
COPY aegis/ aegis/
COPY config/ config/
COPY scenarios/ scenarios/
COPY runbooks/ runbooks/
COPY voices/ voices/
RUN pip install --no-cache-dir --no-deps .
COPY --from=web /web/dist web/dist
# Run as an ordinary user, never as root.
RUN useradd --create-home --uid 10001 aegis && mkdir /data && chown aegis /data
USER 10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/config')"
# Inside a container the server must listen on all interfaces. Set AEGIS_API_TOKEN when you publish the port.
CMD ["aegis", "serve", "--host", "0.0.0.0"]
