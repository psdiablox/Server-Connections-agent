FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY collector ./collector

RUN useradd --uid 10002 --no-create-home --shell /usr/sbin/nologin trace
USER trace

CMD ["python", "-m", "collector.main"]
