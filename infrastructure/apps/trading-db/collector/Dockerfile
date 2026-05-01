FROM python:3.12-slim

WORKDIR /app

RUN adduser --system --no-create-home collector

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

USER collector

CMD ["python", "-u", "main.py"]
