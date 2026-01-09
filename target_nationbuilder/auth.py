import requests
import json
from datetime import datetime, timedelta
from hotglue_etl_exceptions import InvalidCredentialsError


class NationBuilderAuth(requests.auth.AuthBase):
    def __init__(self, target):
        self._target = target
        self.__session = requests.Session()
        self.__access_token = None
        self.__expires_at = None

    def ensure_access_token(self):
        if self.__access_token is None or self.__expires_at <= datetime.utcnow():
            response = self.__session.post(
                f"https://{self._target._config.get('subdomain')}.nationbuilder.com/oauth/token",
                data={
                    "client_id": self._target._config.get('client_id'),
                    "client_secret": self._target._config.get('client_secret'),
                    "refresh_token": self._target._config.get('refresh_token'),
                    "grant_type": "refresh_token",
                },
            )

            if response.status_code >= 400 and response.status_code < 500 and "invalid_grant" in response.text:
                try:
                    error_data = json.loads(response.text)
                    error_message = error_data["error_description"]
                except:
                    error_message = response.text
                raise InvalidCredentialsError(error_message)

            if response.status_code != 200:
                raise Exception(response.text)

            data = response.json()

            self.__access_token = data["access_token"]
            self._target._config["refresh_token"] = data["refresh_token"]
            self._target._config["expires_in"] = data["expires_in"]
            self._target._config["access_token"] = data["access_token"]

            with open(self._target._config_file_path, "w") as outfile:
                json.dump(self._target._config, outfile, indent=4)

            self.__expires_at = datetime.utcnow() + timedelta(
                seconds=int(data["expires_in"]) - 10
            )  # pad by 10 seconds for clock drift

    def __call__(self, r):
        self.ensure_access_token()
        return self.__access_token
