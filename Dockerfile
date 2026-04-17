# syntax=docker/dockerfile:1
FROM python:3.10-slim

# ── 时区 ─────────────────────────────────────────────────────────────────
ENV TZ=Asia/Shanghai
RUN apt-get update && apt-get install -y --no-install-recommends tzdata \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime \
    && echo $TZ > /etc/timezone \
    && rm -rf /var/lib/apt/lists/*

# ── 工作目录 ──────────────────────────────────────────────────────────────
WORKDIR /app

# ── 依赖安装（利用 Docker 层缓存，先只复制 requirements） ─────────────────
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── 源码 ──────────────────────────────────────────────────────────────────
COPY . .

# ── 默认启动（可被 docker-compose command 覆盖） ──────────────────────────
# FastAPI:   uvicorn app.main:app --host 0.0.0.0 --port 8000
# Celery:    celery -A app.tasks.celery_app.celery_app worker --loglevel=info
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
