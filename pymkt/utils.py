import argparse
import toml
from requests.utils import CaseInsensitiveDict


class Config:
    def __init__(self, file):
        self._config = CaseInsensitiveDict(toml.load(file))

    def get(self, tracker, key):
        return (
            self._config.get(tracker.name, {}).get(key)
            or self._config.get(tracker.abbrev, {}).get(key)
            or self._config.get("default", {}).get(key)
        )
