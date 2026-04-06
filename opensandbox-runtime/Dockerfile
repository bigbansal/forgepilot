FROM node:22-bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    bubblewrap \
    ca-certificates \
    curl \
    git \
    python3 \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

RUN npm install -g @google/gemini-cli @openai/codex @anthropic-ai/claude-code \
    && ln -sf "$(command -v gemini)" /usr/local/bin/gemini-cli \
    && ln -sf "$(command -v codex)" /usr/local/bin/codex-cli \
    && ln -sf "$(command -v claude)" /usr/local/bin/claude-code

CMD ["bash", "-lc", "sleep infinity"]
