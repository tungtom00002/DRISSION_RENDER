FROM python:3.11-slim

# Cài chromium MỚI NHẤT có trong kho Debian (không pin để tránh lỗi "not found")
RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

EXPOSE 10000
CMD ["python", "app.py"]
