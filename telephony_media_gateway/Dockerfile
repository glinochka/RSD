FROM node:20-bullseye-slim

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm install --omit=dev

COPY tsconfig.json ./
COPY proto ./proto
COPY src ./src
COPY scripts/download_vad_model.mjs ./scripts/

RUN mkdir -p models && node scripts/download_vad_model.mjs

EXPOSE 8200

HEALTHCHECK --interval=10s --timeout=5s --retries=5 \
  CMD node -e "fetch('http://127.0.0.1:8200/health').then(r=>{if(!r.ok)process.exit(1)}).catch(()=>process.exit(1))"

CMD ["npx", "tsx", "src/server.ts"]
