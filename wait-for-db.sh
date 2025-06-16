#!/bin/sh

echo "⏳ Waiting for MySQL to be ready..."

while ! nc -z db 3306; do
  sleep 1
done

echo "✅ MySQL is ready. Starting app..."
exec python app.py
