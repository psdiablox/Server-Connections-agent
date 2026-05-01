FROM python:3.12-slim

WORKDIR /app

RUN adduser --system --no-create-home frontend

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

USER frontend

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
