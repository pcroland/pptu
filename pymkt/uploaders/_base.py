from abc import ABC, abstractmethod
from http.cookiejar import MozillaCookieJar

import requests
from platformdirs import PlatformDirs
from requests.adapters import HTTPAdapter, Retry

from pymkt.utils import Config


class Uploader(ABC):
    name = None
    abbrev = None
    require_passkey = True

    def __init__(self):
        self.dirs = PlatformDirs(appname="pymkt", appauthor=False)

        config = Config(self.dirs.user_config_path / "config.toml")

        cookies_path = self.dirs.user_data_path / "cookies" / f"{self.name.lower()}.txt"
        if not cookies_path.exists():
            cookies_path = self.dirs.user_data_path / "cookies" / f"{self.abbrev.lower()}.txt"
        if not cookies_path.exists():
            print(
                f"[yellow][bold]WARNING[/bold]: No cookies found for tracker {self.name}, upload will most likely fail"
            )

        jar = MozillaCookieJar(self.dirs.user_data_path / "cookies" / f"{self.name.lower()}.txt")
        jar.load(ignore_expires=True, ignore_discard=True)

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
            "all": config.get(self, "proxy"),
        }

    @abstractmethod
    def upload(self, path, mediainfo, snapshots, thumbnails, *, auto):
        ...
