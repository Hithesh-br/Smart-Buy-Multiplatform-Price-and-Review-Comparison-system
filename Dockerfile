# Use official Playwright Python image containing pre-installed Chromium, Firefox, and system dependencies
FROM mcr.microsoft.com/playwright/python:v1.42.0-jammy

# Set working directory
WORKDIR /app

# Set environment variables for Python
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=5000 \
    MEESHO_HEADLESS=true

# Copy dependency files
COPY requirements.txt .

# Install dependencies including gunicorn for production
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir gunicorn

# Install browser binaries if needed
RUN python -m playwright install chromium firefox

# Copy the rest of the application code
COPY . .

# Expose the application port
EXPOSE 5000

# Run with Gunicorn WSGI server (4 workers, threads, timeout suited for scrapers)
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--threads", "4", "--timeout", "120", "app:app"]
