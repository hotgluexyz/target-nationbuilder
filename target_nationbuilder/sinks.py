"""Nationbuilder target sink class, which handles writing streams."""

from target_nationbuilder.client import NationBuilderSink


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
                    address_type = "registered_address"
                elif i == 1:
                    address_type = "billing_address"
                elif i == 2:
                    address_type = "home_address"
                elif i == 3:
                    address_type = "work_address"
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

        # All of the custom fields in nationbuilder are stored at base level
        if "custom_fields" in record and isinstance(record["custom_fields"], list):
            for custom_field in record["custom_fields"]:
                payload[custom_field["name"]] = custom_field["value"]

        return {"person": payload}  # return payload

    def preprocess_record(self, record: dict, context: dict) -> dict:
        payload = self.map_fields(record)
        return payload


class CustomersSink(ContactsSink):
    name = "Customers"
