# syntax=docker/dockerfile:1

# ---- Dependencies (cached as long as the lockfile does not change) ----
FROM node:26-alpine@sha256:6bd9ab43c0ec0190ca7b2d193906cb8b7edf6e7f4afa43ddeccd6452710bffb5 AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

# ---- Build the Angular application ----
FROM deps AS build
COPY . .
RUN npx ng build --configuration production

# ---- Runtime: static files served by unprivileged Nginx ----
FROM nginxinc/nginx-unprivileged:1.31-alpine@sha256:b5047b9b76845eac124358373c6852377c52e4b05834a47647e955dd91cb8f1e AS runtime

LABEL org.opencontainers.image.title="taskflow-frontend" \
      org.opencontainers.image.description="TaskFlow Angular single-page application"

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist/frontend/browser /usr/share/nginx/html

EXPOSE 8080

HEALTHCHECK --interval=10s --timeout=3s --retries=5 \
    CMD wget -qO- http://127.0.0.1:8080/ >/dev/null || exit 1
