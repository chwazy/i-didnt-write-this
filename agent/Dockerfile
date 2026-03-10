FROM node:20-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends git curl ca-certificates jq sudo && \
    rm -rf /var/lib/apt/lists/*

RUN npm install -g @anthropic-ai/claude-code

# Create non-root user for Claude CLI (refuses to run as root with --dangerously-skip-permissions)
RUN useradd -m -s /bin/bash agent && \
    echo "agent ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

WORKDIR /workspace
RUN chown agent:agent /workspace

USER agent

ENTRYPOINT ["/entrypoint.sh"]
