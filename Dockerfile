FROM python:3.11-slim

# Minimal baseline-friendly image; install git for tests, then drop privileges
RUN useradd -m appuser \
    && apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*
USER appuser
WORKDIR /work

# Preinstall project and common dev tools to speed up container start
COPY --chown=appuser:appuser . /work
RUN python -m pip install --upgrade --user pip && \
    python -m pip install --user -e . && \
    python -m pip install --user -U pytest pytest-cov ruff black isort mypy bandit

RUN python --version || true
ENV PATH="/home/appuser/.local/bin:${PATH}"
