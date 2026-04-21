# syntax=docker/dockerfile:1

# ── Stage 1: 构建静态文件 ────────────────────────────────────────────────
FROM node:20-alpine AS build
WORKDIR /app
COPY package.json .
RUN npm install
COPY . .
RUN npm run build   # 输出到 /app/dist

# ── Stage 2: nginx 服务 ──────────────────────────────────────────────────
FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
