# Используем официальный образ Python 3.11
FROM python:3.11-slim

# Устанавливаем рабочую директорию внутри контейнера
WORKDIR /app

# Обновляем pip и устанавливаем зависимости
RUN pip install --upgrade pip

# Копируем файлы зависимостей
COPY requirements.txt .

# Устанавливаем зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь проект внутрь контейнера
COPY . .

# Экспортируем порт, который будет слушать uvicorn
EXPOSE 5777

# Команда запуска FastAPI приложения
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "5777", "--reload"]