FROM python:3.11-slim-buster

ENV PYTHONIOENCODING=utf-8
ENV LANG=C.UTF-8

WORKDIR /redalert

# install packages
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    nano

COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
  && pip install --no-cache-dir -r requirements.txt

# Create working directory
RUN mkdir /opt/redalert
COPY . .

ENTRYPOINT ["python3", "redalert.py"]
