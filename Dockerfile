FROM ubuntu:18.04

ENV PYTHONIOENCODING=utf-8
ENV LANG=C.UTF-8

#install pip3
RUN apt update

RUN apt install -yqq python3-pip

#install python paho-mqtt client and urllib3
COPY requirements.txt requirements.txt
RUN pip3 install --upgrade pip setuptools --no-cache-dir && \
    pip3 install -r requirements.txt --no-cache-dir


#Create working directory
RUN mkdir /opt/redalert
COPY redalert.py /opt/redalert


ENTRYPOINT ["/usr/bin/python3", "/opt/redalert/redalert.py"]
