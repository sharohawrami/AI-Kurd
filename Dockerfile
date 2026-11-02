FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV KAISH_DATA_DIR=/data \
    KAISH_SECURE_COOKIES=1 \
    KAISH_PROXY=1 \
    PYTHONUNBUFFERED=1
VOLUME /data
EXPOSE 8000
# First start: copies the seeded database (with the superadmin account) into the volume if it's empty.
CMD ["sh", "-c", "mkdir -p /data && [ -f /data/kaish.db ] || cp instance/kaish.db /data/ 2>/dev/null; exec gunicorn -w 2 --threads 4 -b 0.0.0.0:${PORT:-8000} app:app"]
