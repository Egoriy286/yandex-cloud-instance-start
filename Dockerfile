# Используем официальный образ Python 3.11
FROM python:3.11-slim

# Обновляем pip и устанавливаем зависимости
RUN pip install --upgrade pip

# Копируем файлы зависимостей
COPY requirements.txt .

# Устанавливаем зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь проект внутрь контейнера
COPY . .

# Экспортируем порт
EXPOSE 5777

# Указываем команду запуска
CMD ["python3", "app.py"]
