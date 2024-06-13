"""Nationbuilder target sink class, which handles writing streams."""


from target_nationbuilder.client import NationBuilderSink

class ContactsSink(NationBuilderSink):
    """Nationbuilder target sink class."""
    name = "Contacts"
    endpoint = "people"
    entity = "person"
    def map_fields(self, record: dict) -> dict:
        payload  = {
            "full_name": record["name"],
            "first_name": record["first_name"],
            "last_name": record["last_name"],
            "email": record["email"],
            "email_opt_in":True, #disable if requested
            "profile_image_url_ssl":record['photo_url'],
            "note": record["description"],
        }
        # map addresses
        if "addresses" in record and isinstance(record["addresses"], list):
            address_type = None
            for i,address in enumerate(record["addresses"]):
                if i == 0:
                    address_type = "registered_address"
                elif i == 1:
                    address_type = "billing_address"
                elif i == 2:
                    address_type = "home_address"        
                elif i == 3:
                    address_type = "work_address"        
                address_dict = {
                    "address1": address["line1"],
                    "address2": address["line2"],
                    "address3": address["line3"],
                    "city": address["city"],
                    "state": address["state"],
                    "zip": address["postal_code"],
                }
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
                if phone["type"] == "primary":
                    payload["phone"] = phone["number"] 
                if phone["type"] == "work":
                    payload["work_phone_number"] = phone["number"] 
        if "id" in record:
            self.id = record["id"]
            payload["id"] = record["id"]  
        #All of the custom fields in nationbuilder are stored at base level    
        if "custom_fields" in record and isinstance(record["custom_fields"], list):
            for custom_field in record["custom_fields"]:
                payload[custom_field['name']] = custom_field['value']
                     
        return {"person": payload} #return payload
    def preprocess_record(self, record: dict, context: dict) -> dict:
        payload = self.map_fields(record)
        return payload
class CustomersSink(ContactsSink):
    name = "Customers"