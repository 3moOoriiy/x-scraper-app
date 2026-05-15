# =============================================================
# X Posts Scraper - FastAPI Backend
# Includes headless Chrome for keyword/hashtag search via Selenium
# =============================================================
FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DEBIAN_FRONTEND=noninteractive

# Install system deps + Chromium + driver
RUN apt-get update && apt-get install -y --no-install-recommends \
        wget gnupg ca-certificates fonts-liberation \
        libnss3 libxss1 libasound2 \
        libatk-bridge2.0-0 libatk1.0-0 libcups2 libdbus-1-3 \
        libgtk-3-0 libx11-xcb1 libxcomposite1 libxdamage1 libxrandr2 \
        xdg-utils libdrm2 libgbm1 libxkbcommon0 \
        chromium chromium-driver \
    && rm -rf /var/lib/apt/lists/*

# Tell Selenium where to find binaries
ENV CHROME_BIN=/usr/bin/chromium \
    CHROMEDRIVER_PATH=/usr/bin/chromedriver

WORKDIR /app

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .

# Render uses $PORT
ENV PORT=8000
EXPOSE 8000

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
