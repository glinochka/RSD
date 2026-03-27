# Stage 1: Build the Vite app (env vars baked in at build time)
FROM node:20-alpine AS builder

WORKDIR /app

# Build-time API URL (browser). Empty = same-origin (paths in app already start with /api).
ARG VITE_API_BASE_URL=
ARG VITE_API_TIMEOUT=30000
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
ENV VITE_API_TIMEOUT=${VITE_API_TIMEOUT}

COPY package.json package-lock.json* ./
RUN npm ci

COPY . .
RUN npm run build

# Stage 2: Serve with Nginx (production)
FROM nginx:alpine

# Remove default config and copy our SPA config
RUN rm /etc/nginx/conf.d/default.conf
COPY nginx.conf /etc/nginx/conf.d/default.conf

COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
