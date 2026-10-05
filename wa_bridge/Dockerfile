FROM node:20-bookworm-slim

WORKDIR /app

# baileys pulls libsignal from GitHub; npm needs git, but GitHub SSH hangs in Docker.
RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && git config --global url."https://github.com/".insteadOf "ssh://git@github.com/" \
    && git config --global url."https://github.com/".insteadOf "git@github.com:"

ENV GIT_TERMINAL_PROMPT=0

COPY package.json ./
RUN npm install --omit=dev --no-audit --no-fund

COPY server.js ./

EXPOSE 8090

CMD ["node", "server.js"]
