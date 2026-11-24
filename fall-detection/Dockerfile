FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    SPARK_HOME=/opt/spark \
    JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64

RUN apt-get update && apt-get install -y --no-install-recommends \
      openjdk-17-jre-headless tini procps curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
      numpy==2.1.3 pandas==2.2.3 scikit-learn==1.5.2 joblib==1.4.2 \
      pyspark==3.5.3 psycopg[binary]==3.2.3 kafka-python==2.0.2

WORKDIR /app
COPY src/ /app/src/
RUN mkdir -p /app/runtime /app/models
ENV PYTHONPATH=/app/src

CMD ["python", "--version"]
