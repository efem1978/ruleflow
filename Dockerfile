FROM python:3.11-slim

# Minimal baseline-friendly image (non-root)
RUN useradd -m appuser
USER appuser

RUN python --version || true
