FROM python:3.10-slim

# Установка системных зависимостей для сборки некоторых библиотек
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Создаем папку для загрузок
RUN mkdir -p temp_uploads

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]