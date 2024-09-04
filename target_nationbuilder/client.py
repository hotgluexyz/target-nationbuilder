from target_hotglue.client import HotglueSink
import requests
from singer_sdk.plugin_base import PluginBase
from typing import Dict, List, Optional
import singer
import json
import os
import requests
from target_nationbuilder.auth import NationBuilderAuth
from singer_sdk.exceptions import FatalAPIError, RetriableAPIError

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
    country_codes = None

    @property
    def base_url(self):
        return f"https://{self.config.get('subdomain')}.nationbuilder.com/api/v1/"

    def get_country_codes(self):
        if not self.country_codes:
            with open(os.path.join(__location__, "country_codes.json"), "r") as file:
                self.country_codes = json.load(file)
        return self.country_codes

    def get_access_token(self):
        r = requests.Session()
        auth = self.__auth(r)
        return auth

    def get_country_code(self, country_name):
        return self.get_country_codes().get(country_name)

    def validate_response(self, response: requests.Response) -> None:
        """Validate HTTP response."""
        if response.status_code in [409]:
            msg = response.reason
            raise FatalAPIError(msg)
        elif response.status_code in [429] or 500 <= response.status_code < 600:
            msg = self.response_error_message(response)
            raise RetriableAPIError(msg, response)
        elif 400 <= response.status_code < 500:
            try:
                msg = response.text
            except:
                msg = self.response_error_message(response)
            raise FatalAPIError(msg)

    def upsert_record(self, record: dict, context: dict):
        method = "POST"
        state_dict = dict()
        payload = record.get("person") or dict()
        id = payload.get("id")
        self.params["access_token"] = self.get_access_token()
        endpoint = self.endpoint
        if not id:
            try:
                # check if there's a match with the same email
                resp = self.request_api(
                    "GET",
                    request_data=record,
                    endpoint=endpoint + f"/match?email={payload.get('email')}",
                )
                match = resp.json()
                if match.get("person"):
                    id = match["person"]["id"]
            except:
                pass

        if id:
            method = "PUT"
            endpoint = f"{endpoint}/{id}"
        lists = record["person"].pop("lists") if "lists" in record["person"] else None
        response = self.request_api(method, request_data=record, endpoint=endpoint)
        if response.status_code in [200, 201]:
            state_dict["success"] = True
            id = response.json().get(self.entity, {}).get("id")
            record["id"] = id
            if lists:
                record["lists"] = lists
            self.resolve_contact_lists(record)
        # Updating records doesn't seem to work
        if response.status_code == 200 and method == "PUT":
            state_dict["success"] = True
            state_dict["is_updated"] = True
        return id, response.ok, state_dict

    def resolve_contact_lists(self, record: dict):
        if "lists" in record and isinstance(record["lists"], list) and record["lists"]:
            contact_lists = self.get_contact_lists()
            for list_register in record["lists"]:
                should_add_user = True
                if list_register not in contact_lists:
                    contact_list_id = self.create_contact_list(list_register)
                else:
                    contact_list_id = contact_lists[list_register]["id"]
                    should_add_user = self.check_user_not_on_contact_list(contact_list_id)
                if should_add_user:
                    self.include_person_into_contact_list(contact_list_id,record["id"])

    def get_contact_lists(self) -> dict[str,list]:
        method = "GET"
        self.params["access_token"] = self.get_access_token()
        endpoint = "lists"
        next_page = ""
        contact_lists = {}
        while next_page != None:
            resp = self.request_api(
                method,
                endpoint=endpoint + next_page,
            )
            match = resp.json()
            results = match["results"]
            for result in results:
                # Reference: https://linear.app/hotglue/issue/HGI-6388/[newmode]-create-list-if-not-exist-for-target-nationbuilder#comment-93209fd3
                if result["name"] not in contact_lists:
                    contact_lists[result["name"]] = result
            next_page = match.get("next")
            if next_page:
                next_page = next_page.split(endpoint)[1]

        return contact_lists