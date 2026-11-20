# syntax=docker/dockerfile:1
FROM nginxinc/nginx-unprivileged:1.29-alpine

LABEL org.opencontainers.image.title="taskflow-gateway" \
      org.opencontainers.image.description="TaskFlow API gateway (Nginx reverse proxy)"

COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 8080

HEALTHCHECK --interval=10s --timeout=3s --retries=5 \
    CMD wget -qO- http://127.0.0.1:8080/gateway/health || exit 1
