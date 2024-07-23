import requests
import json
from datetime import datetime, timedelta


class NationBuilderAuth(requests.auth.AuthBase):
    def __init__(self, config):
        self.__config = config
        self.__client_id = config["client_id"]
        self.__client_secret = config["client_secret"]
        self.__redirect_uri = config.get("redirect_uri", "https://hotglue.xyz/callback")
        self.__refresh_token = config["refresh_token"]

        self.__session = requests.Session()
        self.__access_token = None
        self.__expires_at = None

    def ensure_access_token(self):
        if self.__access_token is None or self.__expires_at <= datetime.utcnow():
            response = self.__session.post(
                f"https://{self.__config.get('subdomain')}.nationbuilder.com/oauth/token",
                data={
                    "client_id": self.__client_id,
                    "client_secret": self.__client_secret,
                    "redirect_uri": self.__redirect_uri,
                    "refresh_token": self.__refresh_token,
                    "grant_type": "refresh_token",
                },
            )

            if response.status_code != 200:
                raise Exception(response.text)

            data = response.json()

            self.__access_token = data["access_token"]
            self.__config["refresh_token"] = data["refresh_token"]
            self.__config["expires_in"] = data["expires_in"]
            self.__config["access_token"] = data["access_token"]

            with open("config.json", "w") as outfile:
                json.dump(self.__config, outfile, indent=4)

            self.__expires_at = datetime.utcnow() + timedelta(
                seconds=int(data["expires_in"]) - 10
            )  # pad by 10 seconds for clock drift

    def __call__(self, r):
        self.ensure_access_token()
        return self.__access_token
