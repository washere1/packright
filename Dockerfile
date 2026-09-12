FROM node:20-slim AS frontend-build

WORKDIR /build/frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build


FROM python:3.12-slim

WORKDIR /app

COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend backend
COPY config config
COPY --from=frontend-build /build/frontend/dist frontend/dist

ENV PYTHONUNBUFFERED=1
ENV PACKRIGHT_RUNTIME_DIR=/app/runtime-data

CMD ["sh", "-c", "uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port ${PORT:-8080}"]
