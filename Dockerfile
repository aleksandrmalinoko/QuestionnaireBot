FROM raspberry-pi-chromium-webdriver as builder

WORKDIR /OS_QuestionnaireBot

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Установка зависимостей Python
COPY requirements.txt .
RUN pip install -r requirements.txt

FROM raspberry-pi-chromium-webdriver

COPY --from=builder /opt/venv /opt/venv

# Создание рабочей директории
WORKDIR /OS_QuestionnaireBot

ENV PATH="/opt/venv/bin:$PATH"

# Копирование кода приложения
COPY app /OS_QuestionnaireBot/app

# Запуск приложения
CMD ["python", "-u", "/OS_QuestionnaireBot/app/app.py"]