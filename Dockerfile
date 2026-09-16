FROM python:3.12-slim

WORKDIR /app

COPY app/requirements.txt app/requirements.txt
RUN pip install --no-cache-dir -r app/requirements.txt

COPY . .

ENV PORT=8000
EXPOSE 8000

# 用 sh -c 包一层，保证 $PORT 在容器运行时展开
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
