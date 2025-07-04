"""Nationbuilder target sink class, which handles writing streams."""

from target_nationbuilder.client import NationBuilderSink
import requests


class FallbackSink(NationBuilderSink):
    """Fallback sink for non-idempotent endpoints that passes through the record directly."""

    name = "fallback_sink"

    @property
    def endpoint(self):
        return f"/{self.stream_name}"

    def preprocess_record(self, record: dict, context: dict) -> dict:
        """Process the record."""
        if record.get("properties"):
            record = record["properties"]
        return record

    def upsert_record(self, record: dict, context: dict):
        """Send the record directly to the endpoint specified by the stream name."""
        state_updates = dict()
        method = "POST"
        endpoint = self.endpoint
        pk = self.key_properties[0] if self.key_properties else "id"
        
        if record:
            id = record.pop(pk, None)
            if id:
                method = "PATCH"
                endpoint = f"{endpoint}/{id}"
            
            url = f"{self.base_url}{endpoint}"
            headers = {
                "Authorization": f"Bearer {self.get_access_token()}",
                "Content-Type": "application/json",
            }
            
            response = requests.request(method, url, headers=headers, json=record)
            self.validate_response(response)
            
            response_data = response.json()
            id = response_data.get(pk)
            return id, True, state_updates


class ContactsSink(NationBuilderSink):
    """Nationbuilder target sink class."""

    name = "Contacts"
    endpoint = "people"
    entity = "person"

    def map_fields(self, record: dict) -> dict:
        payload = {
            "full_name": record.get("name"),
            "first_name": record.get("first_name"),
            "last_name": record.get("last_name"),
            "email": record.get("email"),
            "email_opt_in": True,  # disable if requested
            "profile_image_url_ssl": record.get("photo_url"),
            "note": record.get("description"),
            "email_opt_in": record.get("subscribe_status") == "subscribed",
            "prefix": record.get("salutation"),
            "tags": record.get("tags")
        }

        # map addresses
        if "addresses" in record and isinstance(record["addresses"], list):
            address_type = None
            for i, address in enumerate(record["addresses"]):
                if i == 0:
                    address_type = "home_address"
                elif i == 1:
                    address_type = "work_address"
                elif i == 2:
                    address_type = "billing_address"
                address_dict = {
                    "address1": address.get("line1"),
                    "address2": address.get("line2"),
                    "address3": address.get("line3"),
                    "city": address.get("city"),
                    "state": address.get("state"),
                    "zip": address.get("postal_code"),
                }

                country_code = None
                if address.get("country"):
                    if len(address["country"]) > 2:
                        country_code = self.get_country_code(address["country"])
                    elif len(address["country"]) == 2:
                        country_code = address["country"]

                if country_code is not None:
                    address_dict["country_code"] = country_code
                if address_type is not None:
                    payload[address_type] = address_dict

        if "phone_numbers" in record and isinstance(record["phone_numbers"], list):
            for phone in record["phone_numbers"]:
                if phone.get("type") == "primary":
                    payload["phone"] = phone.get("number")
                if phone.get("type") == "mobile":
                    payload["mobile"] = phone.get("number")
                if phone.get("type") == "work":
                    payload["work_phone_number"] = phone.get("number")

        if "id" in record:
            payload["id"] = record["id"]

        if "lists" in record:
            payload["lists"] = record["lists"]

        # All of the custom fields in nationbuilder are stored at base level
        if "custom_fields" in record and isinstance(record["custom_fields"], list):
            for custom_field in record["custom_fields"]:
                payload[custom_field["name"]] = custom_field["value"]

        return {"person": payload}  # return payload

    def preprocess_record(self, record: dict, context: dict) -> dict:
        """Process the record and handle empty field updates if configured."""
        payload = self.map_fields(record)
        person = payload.get("person", {})
        only_upsert_empty_fields = self.config.get("only_upsert_empty_fields", False)
        
        matching_person = None
        if person.get("id"):
            matching_person = self.find_matching_object("id", person["id"])
        elif person.get("email"):
            matching_person = self.find_matching_object("email", person["email"])

        if matching_person:
            person["id"] = matching_person.get("id")
        
            if only_upsert_empty_fields :
                for key, value in person.items():
                    # Nationbuilder API always appends tags on the Contact endpoint
                    if matching_person.get(key) is None or key == "tags":
                        matching_person[key] = value
            else:
                # Update all values in matching_person with values from person
                matching_person.update(person)
        
            person = matching_person
        
        # Recursively clean null values from final payload
        person = self.clean_null_values(person)
        return {"person": person}



class CustomersSink(ContactsSink):
    name = "Customers"
