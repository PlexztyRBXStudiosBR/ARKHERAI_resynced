# ARKHER AI — backend + frontend em uma única imagem honesta.
# Navegador → este serviço → modelo próprio. Nada externo.

FROM node:22-slim AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim AS runtime
WORKDIR /app

# torch em variante CPU (menor; para GPU troque a index conforme docs/TRAINING.md)
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt || true \
 && pip install --no-cache-dir fastapi "uvicorn[standard]" pydantic PyYAML httpx

COPY backend/ backend/
COPY model/ model/
COPY --from=frontend /app/frontend/dist frontend/dist

ENV ARKHER_HOST=0.0.0.0 \
    ARKHER_PORT=8710 \
    ARKHER_DATA_DIR=/app/data \
    PYTHONPATH=/app

VOLUME ["/app/data"]
HEALTHCHECK --interval=30s --timeout=8s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8710/api/health', timeout=6).status==200 else 1)"

EXPOSE 8710
CMD ["python", "-m", "uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8710"]
