# Multi-stage build: compile the React frontend, then serve everything from
# the FastAPI backend as a single container (frontend + API, same origin).

# --- Stage 1: build the frontend --------------------------------------------
FROM node:20-alpine AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# --- Stage 2: backend + static assets ---------------------------------------
FROM python:3.11-slim
WORKDIR /app

# Backend dependencies
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# Backend source
COPY backend/ ./backend/

# Built frontend from stage 1
COPY --from=frontend /app/frontend/dist ./frontend/dist
ENV FRONTEND_DIST=/app/frontend/dist

WORKDIR /app/backend
EXPOSE 8000
# Hosts like Render/Fly inject $PORT; default to 8000 locally.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
