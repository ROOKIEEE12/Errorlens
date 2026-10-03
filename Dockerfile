# Hosted demo / self-hosted API.  docker build -t errorlens-api . && docker run -p 8000:8000 errorlens-api
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY pyproject.toml README.md ./
COPY errorlens ./errorlens
RUN pip install --no-cache-dir ".[api,ocr]"
ENV ERRORLENS_HOME=/data
VOLUME /data
EXPOSE 8000
CMD ["uvicorn", "errorlens.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
