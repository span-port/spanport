# The web UI: built with Node, served by nginx, which also forwards /api to the server.
# Built from the repo root: docker build -f ui/Dockerfile .
FROM node:22.22.3-alpine AS build
WORKDIR /ui
COPY ui/package.json ui/package-lock.json ./
RUN npm ci
COPY ui/ ./
RUN npm run build

FROM nginx:1.30.6-alpine
# nginx fills ${SPANPORT_SERVER_PORT} in the template at start-up.
COPY ui/nginx.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /ui/dist /usr/share/nginx/html
# Run as the image's nginx user: it needs to write the generated config, cache and pid file.
RUN chown -R nginx:nginx /etc/nginx/conf.d /var/cache/nginx \
    && touch /run/nginx.pid && chown nginx:nginx /run/nginx.pid
USER nginx
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://127.0.0.1:8080/ || exit 1
