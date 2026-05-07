FROM python:3.11-slim

WORKDIR /app

# 配置 DNS（解决 Docker build 时 DNS 解析失败）
RUN echo "nameserver 8.8.8.8" > /etc/resolv.conf && \
    echo "nameserver 114.114.114.114" >> /etc/resolv.conf

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
COPY requirements.txt package.json package-lock.json ./
RUN pip install --no-cache-dir -r requirements.txt && npm install

# 复制整个项目
COPY . .

# 设置 Node.js 模块路径（execjs 需要）
ENV NODE_PATH=/app/node_modules
ENV PYTHONUNBUFFERED=1
ENV NODE_ENV=production

EXPOSE 5000

CMD ["python", "web/app.py"]
