# syntax=docker/dockerfile:1

FROM python:3.11.6-slim

WORKDIR /app
COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir --upgrade -r requirements.txt

COPY src /app/src

#CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "5000"]