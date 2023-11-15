# -*- coding: utf-8 -*-
import threading
import paho.mqtt.client as mqtt
import requests
import os
from loguru import logger
import time
import apprise
import json

os.environ['PYTHONIOENCODING'] = 'utf-8'
os.environ['LANG'] = 'C.UTF-8'

# mqtt connection Params
MQTT_HOST = os.getenv('MQTT_HOST', "127.0.0.1")
MQTT_PORT = int(os.getenv('MQTT_PORT', 1883))  # Default port is 1883
MQTT_USER = os.getenv("MQTT_USER", "user")
MQTT_PASS = os.getenv("MQTT_PASS", "password")
MQTT_TOPIC = os.environ.get("MQTT_TOPIC", "redalert")
ALERTS_TOPIC = f"{MQTT_TOPIC}/alerts"
DATA_TOPIC = f"{MQTT_TOPIC}/data"
STATUS_TOPIC = f"{MQTT_TOPIC}/status"

DEBUG_MODE = os.getenv("DEBUG_MODE", 'False').lower() in ('true', '1', 't')
DEBUG_URL = os.getenv("DEBUG_URL", "http://localhost/alerts.json")

ALERTS_REGION = os.getenv("REGION", "*")
NOTIFIERS = os.getenv("NOTIFIERS", "")
INCLUDE_TEST_ALERTS = os.getenv("INCLUDE_TEST_ALERTS", 'False').lower() in ('true', '1', 't')


logger.info(f"Monitoring alerts for: {ALERTS_REGION}")

# Setting Request Headers
GET_ALERT_HEADERS = {'Referer': 'https://www.oref.org.il/',
                     'User-Agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/78.0.3904.97 Safari/537.36",
                     'X-Requested-With': 'XMLHttpRequest'}
ALERTS_URL = 'https://www.oref.org.il/WarningMessages/alert/alerts.json'
if DEBUG_MODE:
    ALERTS_URL = DEBUG_URL

SENT_ALERTS_IDS = {0}


def main():
    # Setting apprise Job Manager
    apprise_jobs = apprise.Apprise()

    # Setting up MqttClient
    mqtt_client = mqtt.Client("redalert")
    mqtt_client.username_pw_set(MQTT_USER, MQTT_PASS)
    mqtt_client.on_connect = on_connect
    mqtt_client.on_disconnect = on_disconnect
    mqtt_client.on_log = on_log  # set client logging
    mqtt_client.loop_start()
    logger.info("Connecting to broker")
    mqtt.Client.connected_flag = False  # create flag in class
    mqtt_client.connect(MQTT_HOST, port=MQTT_PORT, keepalive=3600)

    while not mqtt_client.connected_flag:  # wait in loop
        logger.info("In wait loop")
        time.sleep(1)
    logger.info("in Main Loop")
    mqtt_client.loop_stop()  # Stop loop

    if len(NOTIFIERS) != 0:
        logger.info("Setting Apprise Alert")
        jobs = NOTIFIERS.split()
        for job in jobs:
            logger.info("Adding: " + job)
            apprise_jobs.add(job)

    monitor(mqtt_client, apprise_jobs)


# Check Connection Status
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        client.connected_flag = True  # set flag
        logger.info(f"connected OK Returned code={rc}")
    else:
        if rc == 1:
            logger.error("Connection refused – incorrect protocol version")
        if rc == 2:
            logger.error("Connection refused – invalid client identifier")
        if rc == 3:
            logger.error("Connection refused – server unavailable")
        if rc == 4:
            logger.error("Connection refused – bad username or password")
        if rc == 5:
            logger.error("Connection refused – not authorised")


def on_disconnect(client, userdata, rc):
    logger.info(f"disconnecting reason: {rc}")
    client.connected_flag = False
    client.disconnect_flag = True
    client.connect(MQTT_HOST)


def on_log(client, userdata, level, buf):
    logger.inf(buf)


def alarm_on(mqtt_client: mqtt.Client, apprise_jobs: apprise.Apprise, data: dict):
    mqtt_client.publish(DATA_TOPIC, json.dumps(data["data"]), qos=0, retain=False)
    mqtt_client.publish(ALERTS_TOPIC, json.dumps(data), qos=0, retain=False)
    mqtt_client.publish(STATUS_TOPIC, 'on', qos=0, retain=False)
    if len(NOTIFIERS) != 0:
        logger.info("Alerting using Notifires")
        apprise_jobs.notify(
            body='באזורים הבאים: \r\n ' + ', '.join(data["data"]) + '\r\n' + str(data["desc"]),
            title=str(data["title"]),
        )


def alarm_off(mqtt_client: mqtt.Client):
    mqtt_client.publish(STATUS_TOPIC, "No active alerts", qos=0, retain=False)


def is_test_alert(alert):
    # if includes, all alerts are treated as not test
    return not INCLUDE_TEST_ALERTS and ('בדיקה' in alert['data'] or 'בדיקה מחזורית' in alert['data'])


def monitor(mqtt_client, apprise_jobs):
    # start the timer
    threading.Timer(1, monitor, args=([mqtt_client, apprise_jobs])).start()

    try:
        # Check for Alerts
        with requests.get(ALERTS_URL, headers=GET_ALERT_HEADERS) as r:
            r.encoding = 'utf-8-sig'
            alert_data = r.text

        # Check if data contains alert data
        alert_data = alert_data.strip()

        if alert_data:
            alert = json.loads(alert_data)
            if ALERTS_REGION in alert["data"] or ALERTS_REGION == "*":
                if (alert["id"] not in SENT_ALERTS_IDS and not is_test_alert(alert)) or DEBUG_MODE:
                    SENT_ALERTS_IDS.add(alert["id"])
                    alarm_on(mqtt_client, apprise_jobs, alert)
                    logger.info(json.dumps(alert))
        else:
            alarm_off(mqtt_client)
    except Exception as ex:
        logger.critical(f"Exception in monitor: {ex}")


if __name__ == '__main__':
    main()
