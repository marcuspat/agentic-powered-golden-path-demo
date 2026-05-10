# Multi-stage build for the {{ appName }} Golden Path service.
# Stage 1: install production deps in an isolated builder image.
FROM node:20-alpine AS builder
WORKDIR /build
COPY package*.json ./
RUN npm ci --omit=dev

# Stage 2: minimal runtime image.
FROM node:20-alpine AS runtime
ENV NODE_ENV=production
WORKDIR /app
COPY --from=builder /build/node_modules ./node_modules
COPY package*.json ./
COPY index.js ./

USER node
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD wget -qO- http://127.0.0.1:8080/healthz || exit 1

CMD ["node", "index.js"]
