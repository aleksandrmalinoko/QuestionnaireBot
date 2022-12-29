FROM python:3.10-buster as builder

WORKDIR /OS_QuestionnaireBot

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install -r requirements.txt

FROM python:3.10-slim-buster

COPY --from=builder /opt/venv /opt/venv

WORKDIR /OS_QuestionnaireBot

ENV PATH="/opt/venv/bin:$PATH"

COPY app /OS_QuestionnaireBot/app

CMD ["python", "-u", "/OS_QuestionnaireBot/app/app.py"]