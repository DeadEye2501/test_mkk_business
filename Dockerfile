FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /service
RUN pip install --no-cache-dir pipenv
COPY Pipfile Pipfile.lock ./
RUN pipenv install --system --deploy
COPY . .
