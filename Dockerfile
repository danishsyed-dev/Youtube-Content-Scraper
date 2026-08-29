# syntax=docker/dockerfile:1

# ---- YouTube Content Scraper ---------------------------------------------
# Ships Chromium + a matching driver so Selenium works out of the box.
# Runs under gunicorn as a non-root user.
FROM python:3.12-slim

# Chromium and the libraries it needs to run headless in a container.
# python3-selenium's own dependencies plus fonts for correct rendering.
RUN apt-get update && apt-get install -y --no-install-recommends \
      chromium \
      chromium-driver \
      fonts-liberation \
      ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Selenium/Chrome configuration for containers.
ENV CHROME_BINARY=/usr/bin/chromium \
    HEADLESS=true \
    HOST=0.0.0.0 \
    PORT=8000 \
    OUTPUT_DIR=/app/output \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Selenium Manager may need to place a driver; make chromium-driver visible.
ENV PATH="/usr/lib/chromium:${PATH}"

# Run as non-root.
RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /app/output \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health').status==200 else 1)"

# One worker with threads: scrapes run on background threads within the worker,
# and job state is in-memory (single process). Increase threads, not workers,
# unless you move job state to shared storage.
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "1", "--threads", "8", \
     "--timeout", "300", "app:app"]
