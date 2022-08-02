from abc import ABC, abstractmethod
from http.cookiejar import MozillaCookieJar

import requests
from platformdirs import PlatformDirs
from requests.adapters import HTTPAdapter, Retry
from ruamel.yaml import YAML


class Uploader(ABC):
    def __init__(self, name):
        self.dirs = PlatformDirs(appname="pymkt", appauthor=False)

        config = YAML().load(self.dirs.user_config_path / "config.yml")

        jar = MozillaCookieJar(self.dirs.user_data_path / "cookies" / f"{name.lower()}.txt")
        jar.load()

        self.session = requests.Session()
        for scheme in ("http://", "https://"):
            self.session.mount(
                scheme,
                HTTPAdapter(
                    max_retries=Retry(
                        total=5,
                        backoff_factor=1,
                        allowed_methods=["DELETE", "GET", "HEAD", "OPTIONS", "POST", "PUT", "TRACE"],
                        status_forcelist=[429, 500, 502, 503, 504],
                        raise_on_status=False,
                    ),
                ),
            )
        self.session.cookies = jar
        self.session.proxies = {
            "all": config.get("proxy", {}).get(name.lower()),
        }

    @abstractmethod
    def upload(self, path, mediainfo, snapshots, thumbnails, *, auto):
        ...
