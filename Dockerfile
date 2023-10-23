FROM python:3.11.3-slim

ENV PYTHONUNBUFFERED 1

WORKDIR /bot

RUN apt-get update \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip
COPY ./requirements.txt /bot/
RUN pip install --no-cache-dir --upgrade -r /bot/requirements.txt


COPY . /bot

CMD [ "python","main.py" ]
