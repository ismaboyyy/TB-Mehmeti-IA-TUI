FROM python:3.11-slim

# Dépendances système (PyMuPDF + build de sentence-transformers)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# torch en version CPU : évite le téléchargement de ~3 Go de librairies CUDA
# inutiles (pas de GPU dans ce conteneur). Installé AVANT requirements.txt pour
# que sentence-transformers / FlagEmbedding réutilisent ce torch.
RUN pip install --no-cache-dir torch==2.5.1 \
    --index-url https://download.pytorch.org/whl/cpu

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
