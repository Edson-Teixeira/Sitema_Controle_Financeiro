#!/bin/sh

set -e

echo "Aplicando migrações do banco de dados..."
python manage.py migrate --noinput

echo "Coletando arquivos estáticos..."
python manage.py collectstatic --noinput

echo "Semeando dados iniciais..."
python manage.py seed_data || true

echo "Iniciando servidor Gunicorn..."
exec gunicorn core.wsgi:application --bind 0.0.0.0:8000

