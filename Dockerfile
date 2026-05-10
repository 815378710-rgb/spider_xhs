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

# Python依赖（FastAPI版）
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# JS签名依赖（crypto-js, jsdom）
COPY package.json package-lock.json* ./
RUN npm install 2>/dev/null || npm install --legacy-peer-deps

# 复制整个项目
COPY . .

# 设置 Node.js 模块路径（execjs 需要）
ENV NODE_PATH=/app/node_modules
ENV PYTHONUNBUFFERED=1
ENV NODE_ENV=production

EXPOSE 5005

CMD ["python", "backend/main.py"]
