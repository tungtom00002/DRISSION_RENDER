FROM python:3.11-slim

# Cài Chromium, xvfb, xauth và các thư viện X11 cần thiết cho headed mode
RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium \
    fonts-liberation \
    xvfb \
    xauth \
    x11-xkb-utils \
    xfonts-100dpi \
    xfonts-75dpi \
    xfonts-scalable \
    xfonts-cyrillic \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 10000
CMD ["python", "app.py"]
