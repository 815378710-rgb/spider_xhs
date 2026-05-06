FROM python:3.11-slim

WORKDIR /app

# 系统依赖：Node.js（签名算法需要）+ OpenCV 依赖
RUN apt-get update && apt-get install -y \
    curl \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# 先复制依赖文件，利用 Docker 缓存
COPY web/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && npm install -g crypto-js jsdom

# 复制整个项目（签名JS和API层都依赖）
COPY . .

WORKDIR /app/web

EXPOSE 5000

ENV PYTHONUNBUFFERED=1
ENV NODE_ENV=production

CMD ["python", "app.py"]
