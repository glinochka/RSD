FROM node:20-bullseye-slim

WORKDIR /app

COPY package.json ./
RUN npm install --omit=dev

COPY server.js ./

EXPOSE 8090

CMD ["node", "server.js"]
