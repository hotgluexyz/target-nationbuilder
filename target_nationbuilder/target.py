"""Nationbuilder target class."""

from singer_sdk import typing as th
from singer_sdk.sinks import Sink
from target_hotglue.target import TargetHotglue
from typing import Type

from target_nationbuilder.sinks import (
    ContactsSink,
    FallbackSink,
)


class TargetNationbuilder(TargetHotglue):
    """Sample target for Nationbuilder."""

    SINK_TYPES = [
        ContactsSink,
        FallbackSink,
    ]
    name = "target-nationbuilder"

    def __init__(
        self,
        config=None,
        parse_env_config: bool = False,
        validate_config: bool = True,
        state: str = None,
    ) -> None:
        self.config_file = config[0]
        super().__init__(
            config=config,
            parse_env_config=parse_env_config,
            validate_config=validate_config,
        )

    config_jsonschema = th.PropertiesList(
        th.Property("client_id", th.StringType, required=True),
        th.Property("client_secret", th.StringType, required=True),
        th.Property("refresh_token", th.StringType, required=True),
        th.Property("subdomain", th.StringType, required=True),
        th.Property("only_upsert_empty_fields", th.BooleanType, required=False),
    ).to_dict()

    def get_sink_class(self, stream_name: str) -> Type[Sink]:
        sink = super().get_sink_class(stream_name)
        return sink if sink else FallbackSink

if __name__ == "__main__":
    TargetNationbuilder.cli()
