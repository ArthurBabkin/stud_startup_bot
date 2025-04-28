# Используем официальный Python-образ
FROM python:3.11-slim

# Устанавливаем рабочую директорию
WORKDIR /app

# Устанавливаем зависимости для PostgreSQL
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Копируем файлы проекта
COPY . .

# Устанавливаем зависимости Python
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Указываем переменные окружения для Python
ENV PYTHONUNBUFFERED=1

# Запускаем бота
CMD ["python", "-m", "app.main"]