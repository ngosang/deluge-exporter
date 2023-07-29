#!/usr/bin/env python3
import logging
import os
import sys
import time

import prometheus_client
import prometheus_client.core
import requests


class DelugeCollector(object):
    def __init__(self, deluge_url: str, deluge_password: str):
        self.deluge_api_url = (deluge_url if deluge_url.endswith('/') else deluge_url + '/') + 'json'
        self.deluge_password = deluge_password
        self.session = requests.Session()
        self.metrics = {}
        self.get_deluge_stats()

    def collect(self):
        try:
            deluge_stats = self.get_deluge_stats()
        except Exception as e:
            logging.error(e)
            return

        # torrents by state
        deluge_torrent_state_count = prometheus_client.core.GaugeMetricFamily(
            "deluge_torrent_state_count", "Number of torrents by state", labels=["state"])
        for state in deluge_stats["filters"]["state"]:
            deluge_torrent_state_count.add_metric([state[0].lower()], state[1])
        yield deluge_torrent_state_count

        # torrents by label
        deluge_torrent_label_count = prometheus_client.core.GaugeMetricFamily(
            "deluge_torrent_label_count", "Number of torrents by label", labels=["label"])
        for label in deluge_stats["filters"].get("label", []):
            deluge_torrent_label_count.add_metric([label[0].lower()], label[1])
        yield deluge_torrent_label_count

        # other stats
        for key, value in deluge_stats["stats"].items():
            # skip string stats like external_ip
            if isinstance(value, int) or isinstance(value, float):
                metric = prometheus_client.core.GaugeMetricFamily(
                    "deluge_" + key.lower(), "Deluge metric " + key)
                metric.add_metric([], value)
                yield metric

    def get_deluge_stats(self) -> dict:
        data = self.get_webui_data()
        if data is None:
            self.get_login()
            data = self.get_webui_data()
        if not data["connected"]:
            self.get_connection()
            data = self.get_webui_data()
        if data is None or not data["connected"]:
            raise Exception(f"Get stats error! Data: {data}")
        return data

    def get_login(self):
        logging.info("Loging in Deluge Web UI...")
        payload = {
            "method": "auth.login",
            "params": [self.deluge_password],
            "id": 1
        }
        response = self.session.post(self.deluge_api_url, json=payload)
        if response.status_code != 200:
            raise Exception(f"Get login error! Bad HTTP Code: {response.status_code} Response: {response.text}")
        response_json = response.json()
        if not response_json["result"]:
            raise Exception(f"Get login error! Bad credentials")
        logging.info("Loging successful!")

    def get_connection(self):
        logging.info("Connecting Deluge Web UI...")
        payload = {
            "method": "web.get_hosts",
            "params": [],
            "id": 1
        }
        response = self.session.post(self.deluge_api_url, json=payload)
        if response.status_code != 200:
            raise Exception(f"Get connection error! Bad HTTP Code: {response.status_code} Response: {response.text}")
        response_json = response.json()
        if not response_json["result"] or len(response_json["result"]) < 1:
            raise Exception(f"Get connection error! Bad response. Response: {response.text}")
        server_id = response_json["result"][0][0]
        payload = {
            "method": "web.connect",
            "params": [server_id],
            "id": 1
        }
        response = self.session.post(self.deluge_api_url, json=payload)
        if response.status_code != 200:
            raise Exception(f"Get connection error! Bad HTTP Code: {response.status_code} Response: {response.text}")
        response_json = response.json()
        if not response_json["result"]:
            raise Exception(f"Get connection error! Bad response. Response: {response.text}")
        logging.info("Connected successful!")

    def get_webui_data(self) -> dict:
        # we use an incorrect label filter to avoid getting torrent data
        payload = {
            "method": "web.update_ui",
            "params": [["label"], {"label": "fake_label"}],
            "id": 1
        }
        response = self.session.post(self.deluge_api_url, json=payload)
        if response.status_code != 200:
            raise Exception(f"Get stats error! Bad HTTP Code: {response.status_code} Response: {response.text}")
        response_json = response.json()
        return response_json["result"]


def main():
    logging.basicConfig(
        format='%(asctime)s %(levelname)-8s %(message)s',
        level=logging.getLevelName(os.environ.get("LOG_LEVEL", "INFO")),
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    logging.info("Starting Deluge Prometheus Exporter ...")

    try:
        deluge_url = os.environ["DELUGE_URL"]
    except Exception:
        logging.error("Configuration error. The environment variable DELUGE_URL is mandatory")
        sys.exit(1)

    try:
        deluge_password = os.environ["DELUGE_PASSWORD"]
    except Exception:
        logging.error("Configuration error. The environment variable DELUGE_PASSWORD is mandatory")
        sys.exit(1)

    exporter_address = os.environ.get("LISTEN_ADDRESS", "0.0.0.0")
    exporter_port = int(os.environ.get("LISTEN_PORT", 8011))

    collector = DelugeCollector(deluge_url, deluge_password)

    prometheus_client.core.REGISTRY.register(collector)
    prometheus_client.start_http_server(exporter_port, exporter_address)

    logging.info("Server listening in http://%s:%d/metrics", exporter_address, exporter_port)
    while True:
        time.sleep(1e9)


if __name__ == "__main__":
    main()
