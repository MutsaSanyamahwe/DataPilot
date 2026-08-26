# Single-stage build -- deliberately not multi-stage. Every dependency in
# requirements.txt (pandas, numpy, pyarrow, etc.) ships prebuilt wheels
# for linux/amd64 and linux/arm64 on PyPI, so there's no compiler step to
# separate out. If you're building for an unusual platform where a wheel
# isn't available, pip will try to compile from source and fail without
# build-essential installed -- uncomment the apt-get line below if you
# hit that.
FROM python:3.12-slim

# PYTHONUNBUFFERED: log output (uvicorn, print statements, tracebacks)
# shows up immediately in `docker logs`, not buffered until the process
# exits or the buffer fills.
# PYTHONDONTWRITEBYTECODE: skip writing .pyc files -- there's no benefit
# to the bytecode cache surviving between container runs, since each
# container starts from the same image layer every time.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# RUN apt-get update && apt-get install -y --no-install-recommends build-essential && rm -rf /var/lib/apt/lists/*

# Copy requirements first, install, THEN copy the rest of the app code --
# this is a Docker layer-caching pattern: as long as requirements.txt
# hasn't changed, `docker build` reuses the cached "pip install" layer
# instead of re-downloading/reinstalling every dependency on every code
# change. Editing app/ask.py shouldn't cost you a multi-minute pandas
# reinstall.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Runs as a non-root user inside the container -- standard hardening
# practice; there's no reason this process needs root privileges, and
# running as root is the default if you don't opt out of it explicitly.
RUN useradd --create-home --uid 1000 appuser && \
    mkdir -p /app/app/storage && \
    chown -R appuser:appuser /app
USER appuser

# See app/config.py: storage_dir defaults to a path INSIDE the app
# package (Path(__file__).parent / "storage"), which resolves to
# /app/app/storage once this image's WORKDIR/COPY layout is in place.
# Declaring it as a VOLUME means `docker run -v` can point it at a real
# persistent location on the host -- without that, every uploaded
# session's parquet file (see sessions/store.py) lives only in this
# container's writable layer and is gone the moment the container is
# removed or recreated. This does NOT set up persistence for you by
# itself; see the accompanying notes for the actual `docker run -v` flag
# needed, and see sessions/store.py's cleanup_expired_sessions() for why
# this being ephemeral is actually fine for a portfolio deployment.
VOLUME ["/app/app/storage"]

EXPOSE 8000

# Hits the app's own /health endpoint using Python's stdlib rather than
# curl/wget -- neither is installed in the slim base image, and adding
# one just for this would bloat the image for no real benefit.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=3)" || exit 1

# GOOGLE_API_KEY (and any other secret in app/config.py's Settings) is
# deliberately NOT set here and NOT baked into the image via a COPYed
# .env file (see .dockerignore) -- pass it at `docker run` time instead,
# e.g. `docker run -e GOOGLE_API_KEY=... ` or `--env-file .env`. Baking a
# secret into an image layer means it's recoverable from that layer
# forever, even after being "removed" in a later layer.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]