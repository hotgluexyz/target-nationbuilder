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
from target_nationbuilder.exceptions import UnableToCreateContactsListError, UnableToIncludePeopleIntoContactsListError, UnableToCheckUserNotOnContactListError, UnableToGetContactListsError
import hashlib
import time
import unidecode
import re


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
        self.__auth = NationBuilderAuth(self._target)

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
        
        if id:
            method = "PUT"
            endpoint = f"{endpoint}/{id}"
        lists = record["person"].pop("lists") if "person" in record and "lists" in record["person"] else None
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
        if "lists" not in record or not isinstance(record["lists"], list) or not record["lists"] or "id" not in record or not record["id"]:
            return
        contact_lists = self.get_contact_lists()
        for list_register in record["lists"]:
            should_add_user = True
            people_id = record["id"]
            if list_register not in contact_lists:
                contact_list_id = self.create_contact_list(list_register, people_id, contact_lists)
            else:
                contact_list_id = contact_lists[list_register]["id"]
                should_add_user = self.check_user_not_on_contact_list(contact_list_id, people_id)
            if should_add_user:
                self.include_person_into_contact_list(contact_list_id, people_id)

    def get_contact_lists(self) -> dict[str,list]:
        try:
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
        except Exception as e:
            raise UnableToGetContactListsError(f"Unable to get contact lists from the nation. {e}")
    
    def create_contact_list(self, contact_list_name: str, author_id: str, contact_lists: dict) -> int:
        try:
            def transform_contact_list_into_slug(contact_list_name: str, contact_lists:dict) -> str:
                slugs = [contact_list["slug"] for contact_list in contact_lists.values() if "slug" in contact_list]
                contact_list_name = contact_list_name.lower()
                contact_list_name = unidecode.unidecode(contact_list_name)
                contact_list_name = re.sub(r'[^a-z0-9]+', '-', contact_list_name)
                contact_list_name = contact_list_name.strip('-')
                contact_list_name = re.sub(r'-+', '-', contact_list_name)
                if contact_list_name not in slugs:
                    return contact_list_name
                unique_element = str(time.time())
                combined_str = contact_list_name + unique_element
                hash_object = hashlib.sha256(combined_str.encode('utf-8'))
                return contact_list_name + hash_object.hexdigest()

            method = "POST"
            self.params["access_token"] = self.get_access_token()
            state_dict = dict()
            endpoint = "lists"
            coantact_list = {
                "list": {
                    "name": contact_list_name,
                    "slug": transform_contact_list_into_slug(contact_list_name, contact_lists),
                    "author_id": author_id
                }
            }
            response = self.request_api(
                method,
                request_data=coantact_list,
                endpoint=endpoint,
            )
            if response.status_code in [200, 201]:
                state_dict["success"] = True
                return response.json().get("list_resource", {}).get("id")
        except Exception as e:
            raise UnableToCreateContactsListError(f"Unable to create contacts list {contact_list_name} with author if {author_id}")
        
    def check_user_not_on_contact_list(self, contact_list_id: int, people_id: int) -> bool:
        try:
            method = "GET"
            self.params["access_token"] = self.get_access_token()
            endpoint = f"lists/{contact_list_id}/people"
            resp = self.request_api(
                method,
                endpoint=endpoint,
            )
            match = resp.json()
            results = match["results"]
            for result in results:
                if people_id == result["id"]:
                    return False
            return True
        except Exception as e:
            raise UnableToCheckUserNotOnContactListError(f"Unable to check if user {people_id} is on contact list {contact_list_id}. {e}")

    
    def include_person_into_contact_list(self, contact_list_id:int, people_id:int):
        try:
            method = "POST"
            self.params["access_token"] = self.get_access_token()
            endpoint = f"lists/{contact_list_id}/people"
            people_ids = {
                "people_ids": [people_id]
            }
            self.request_api(
                method,
                request_data=people_ids,
                endpoint=endpoint,
            )
        except Exception as e:
            raise UnableToIncludePeopleIntoContactsListError(f"Unable to include {people_id} into contact list {contact_list_id}. {e}")

    def find_matching_object(self, lookup_field: str, lookup_value: str):
        """Find a matching object by any lookup field.
        
        Args:
            lookup_field: The field to search on (e.g., 'email', 'id', etc.)
            lookup_value: The value to search for
            
        Returns:
            The full matching object if found, None otherwise
        """
        if not lookup_value:
            return None
            
        try:
            if lookup_field == "id":
                endpoint = f"{self.endpoint}/{lookup_value}"
            else: 
                endpoint = f"{self.endpoint}/match?{lookup_field}={lookup_value}"
            
            resp = self.request_api(
                "GET",
                endpoint=endpoint,
                params={"access_token": self.get_access_token()}
            )
            
            if resp.status_code in [200, 201]:
                match = resp.json()
                if match.get(self.entity):
                    return match[self.entity]
            return None
        except Exception:
            return None

    def clean_null_values(self, data):
        """Recursively clean null values from a dictionary."""
        if not isinstance(data, dict):
            return data
            
        keys_to_remove = []
        for key, value in data.items():
            if value is None:
                keys_to_remove.append(key)
            elif isinstance(value, dict):
                cleaned = self.clean_null_values(value)
                if not cleaned:
                    keys_to_remove.append(key)
                else:
                    data[key] = cleaned
                    
        for key in keys_to_remove:
            data.pop(key)
            
        return data
            