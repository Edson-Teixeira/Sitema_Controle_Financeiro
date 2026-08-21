FROM python:3.11-slim

# Impede escrita de arquivos .pyc e habilita logs em tempo real
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Dependências do sistema (build-essential e libpq para PostgreSQL)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Instalação de pacotes Python
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copia do código fonte da aplicação
COPY . /app/

# Concede permissão de execução ao script de entrada
RUN chmod +x /app/entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]

