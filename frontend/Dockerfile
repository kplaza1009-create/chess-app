FROM node:24-bookworm-slim AS base
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
FROM base AS development
COPY . .
RUN chown -R node:node /app
USER node
EXPOSE 5173
CMD ["npm", "run", "dev"]

FROM base AS build
COPY . .
RUN npm run build

FROM nginxinc/nginx-unprivileged:stable-alpine AS production
ENV PORT=8080 \
    API_UPSTREAM=api:8000 \
    NGINX_ENVSUBST_FILTER="^(PORT|API_UPSTREAM)$"
COPY nginx.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 8080
