FROM python:3.11-slim

WORKDIR /app

# System dependencies for ML libraries
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev libgomp1 && rm -rf /var/lib/apt/lists/*

# Install ML-specific dependencies.
# Default profile is XGBoost-only; set INSTALL_LSTM=1 to include TensorFlow.
ARG INSTALL_LSTM=0
COPY requirements-ml.txt requirements-ml-lstm.txt ./
RUN if [ "$INSTALL_LSTM" = "1" ]; then \
      pip install --no-cache-dir -r requirements-ml-lstm.txt; \
    else \
      pip install --no-cache-dir -r requirements-ml.txt; \
    fi

# Copy ML code + workers + shared config
COPY ml/ ./ml/
COPY workers/ ./workers/
COPY core/ ./core/
COPY db/ ./db/

# MLflow artifacts directory
RUN mkdir -p /app/models /app/reports

# Run Celery ML worker on the "ml" queue
CMD ["celery", "-A", "workers.celery_app", "worker", \
    "-Q", "ml", \
    "--concurrency", "2", \
    "--loglevel", "info"]
