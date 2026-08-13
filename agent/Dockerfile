# Base image provides uv and Python 3.12 (set in build.yaml).
ARG BUILD_FROM=ghcr.io/astral-sh/uv:python3.12-bookworm-slim
FROM $BUILD_FROM

# Extra system packages needed at runtime
# (git for workspace ops, curl/ca-certificates for outbound HTTP)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl \
        git \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install the agent package
RUN uv pip install --system --no-cache nanobot-ai==0.3.0

# Patch nanobot WebUI for Home Assistant ingress (absolute → relative paths)
COPY patches/ingress_fix.py /tmp/ingress_fix.py
RUN python3 /tmp/ingress_fix.py && rm /tmp/ingress_fix.py

# Ensure the agent config directory exists
RUN mkdir -p /root/.nanobot

# Copy startup script
COPY run.sh /run.sh
RUN chmod a+x /run.sh

LABEL \
    io.hass.version="0.3.0" \
    io.hass.type="addon" \
    io.hass.arch="aarch64|amd64"

CMD ["/run.sh"]

