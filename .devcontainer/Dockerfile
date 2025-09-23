FROM mcr.microsoft.com/devcontainers/python:3.11

ARG NODE_VERSION=20.16.0

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl xz-utils \
    && curl -fsSL "https://nodejs.org/dist/v${NODE_VERSION}/node-v${NODE_VERSION}-linux-arm64.tar.xz" \
      | tar -xJ -C /usr/local --strip-components=1 \
    && ln -sf /usr/local/bin/node /usr/local/bin/nodejs \
    && corepack enable \
    && apt-get purge -y --auto-remove xz-utils \
    && rm -rf /var/lib/apt/lists/*
