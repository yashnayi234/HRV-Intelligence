# ── Frontend Dockerfile ───────────────────────────────────────────────────────
# Stage 1: Build React app
FROM node:20-alpine AS builder

WORKDIR /app

COPY package*.json ./
RUN npm ci --silent

COPY . .

# API URL will be injected at build time via GitHub Actions
ARG VITE_API_URL=https://your-api-gateway-url.amazonaws.com
ENV VITE_API_URL=${VITE_API_URL}

RUN npm run build

# Stage 2: Serve with Nginx
FROM nginx:1.25-alpine

# Copy built React app
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy custom Nginx config
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s \
    CMD wget -q --spider http://localhost || exit 1

CMD ["nginx", "-g", "daemon off;"]
