FROM python:3.12-slim

WORKDIR /srv
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Everything the app needs at runtime: app/capacity.py loads analysis/ at import
# time, and the boot-time SQL apply (Railway startCommand) reads scripts/ + db/.
COPY app ./app
COPY dashboard ./dashboard
COPY analysis ./analysis
COPY db ./db
COPY scripts ./scripts

# Default command runs the API; the worker service overrides it in compose.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
