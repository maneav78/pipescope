FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends python3 && rm -rf /var/lib/apt/lists/*
COPY . /app
WORKDIR /app
RUN useradd --no-create-home --system appuser && chown -R appuser:appuser /app
USER appuser
CMD ["python3", "app.py"]