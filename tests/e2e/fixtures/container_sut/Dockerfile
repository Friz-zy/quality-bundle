FROM python:3.12-slim

WORKDIR /app
COPY server.py /app/server.py
ENV APP_MSG=""
EXPOSE 8080
CMD ["python", "server.py"]
