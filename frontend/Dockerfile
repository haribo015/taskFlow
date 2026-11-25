# syntax=docker/dockerfile:1

# ---- Dependencies (cached as long as the lockfile does not change) ----
FROM node:24-alpine@sha256:116b800c3754b440ee0aa3ed2f20f5bf3d99a554bfd9adeea09ea8017f6e85f5 AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

# ---- Build the Angular application ----
FROM deps AS build
COPY . .
RUN npx ng build --configuration production

# ---- Runtime: static files served by unprivileged Nginx ----
FROM nginxinc/nginx-unprivileged:1.29-alpine@sha256:0c79d56aee561a1d81c63f00eee5fb5fe29279560cdc55e91425133104c7fbe6 AS runtime

LABEL org.opencontainers.image.title="taskflow-frontend" \
      org.opencontainers.image.description="TaskFlow Angular single-page application"

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist/frontend/browser /usr/share/nginx/html

EXPOSE 8080

HEALTHCHECK --interval=10s --timeout=3s --retries=5 \
    CMD wget -qO- http://127.0.0.1:8080/ >/dev/null || exit 1
