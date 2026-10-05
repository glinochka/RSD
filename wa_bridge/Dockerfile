FROM node:20-bookworm-slim

WORKDIR /app

# baileys pulls libsignal from GitHub; npm needs git for that install.
RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY package.json ./
RUN npm install --omit=dev

COPY server.js ./

EXPOSE 8090

CMD ["node", "server.js"]
