from target_hotglue.client import HotglueSink
import requests
from singer_sdk.plugin_base import PluginBase
from typing import Dict, List, Optional
import singer
import json
import os
import requests
from target_nationbuilder.auth import NationBuilderAuth

__location__ = os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))
LOGGER = singer.get_logger()


class NationBuilderSink(HotglueSink):
    def __init__(
        self,
        target: PluginBase,
        stream_name: str,
        schema: Dict,
        key_properties: Optional[List[str]],
    ) -> None:
        super().__init__(target, stream_name, schema, key_properties)
        # Save config for refresh_token saving
        self.config_file = target.config
        self.__auth = NationBuilderAuth(dict(self.config))

    """Dynamics target sink class."""
    id = None
    country_codes = None

    @property
    def base_url(self):
        return f"https://{self.config.get('subdomain')}.nationbuilder.com/api/v1/"

    def get_country_codes(self):
        if not self.country_codes:
            with open(os.path.join(__location__, "country_codes.json"), "r") as file:
                self.country_codes = json.load(file)
        return self.country_codes

    def get_auth(self):
        r = requests.Session()
        auth = self.__auth(r)
        return auth

    def get_access_token(self):
        r = requests.Session()
        auth = self.__auth(r)
        return auth

    def get_country_code(self, country_name):
        return self.get_country_codes().get(country_name)

    def log_request_response(self, record, response):
        self.logger.info(f"Sending payload for stream {self.name}: {record}")
        self.logger.info(f"Response: {response.text}")

    def upsert_record(self, record: dict, context: dict):
        method = "POST"
        state_dict = dict()
        id = None
        self.params["access_token"] = self.get_access_token()
        endpoint = self.endpoint
        if self.id:
            method = "PUT"
            endpoint = f"{endpoint}/{self.id}"

        response = self.request_api(method, request_data=record, endpoint=endpoint)
        self.validate_response(response)
        self.log_request_response(record, response)
        if response.status_code in [200, 201]:
            state_dict["success"] = True
            id = response.json().get(self.entity, {}).get("id")
        # Updating records doesn't seem to work
        if response.status_code == 200 and method == "PUT":
            state_dict["is_updated"] = True
        return id, response.ok, state_dict
