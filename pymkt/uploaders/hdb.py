import re
import sys
import time
from http.cookiejar import MozillaCookieJar
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from platformdirs import PlatformDirs
from requests.adapters import HTTPAdapter, Retry
from rich import print
from ruamel.yaml import YAML

from pymkt.uploaders import Uploader


class HDBUploader(Uploader):
    CATEGORY_MAP = {
        "Movie": 1,
        "TV": 2,
    }
    CODEC_MAP = {
        "H.264": 1,
        "HEVC": 5,
        "MPEG-2": 2,
        "VC-1": 3,
        "VP9": 6,
        "XviD": 4,
    }
    MEDIUM_MAP = {
        "Blu-ray/HD-DVD": 1,
        "Capture": 4,
        "Encode": 3,
        "Remux": 5,
        "WEB-DL": 6,
    }

    def upload(self, path, mediainfo, snapshots, thumbnails, *, auto):
        dirs = PlatformDirs(appname="pymkt", appauthor=False)

        config = YAML().load(dirs.user_config_path / "config.yml")

        jar = MozillaCookieJar(dirs.user_data_path / "cookies" / "hdb.txt")
        jar.load()

        session = requests.Session()
        for scheme in ("http://", "https://"):
            session.mount(
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
        session.cookies = jar
        session.proxies = (
            {
                "all": config.get("proxy", {}).get("hdb"),
            },
        )

        if re.search(r"\.S\d+(E\d+)*\.", str(path)):
            print("Detected series")
            category = "TV"
        else:
            print("Detected movie")
            category = "Movie"

        if category == "TV":
            imdb = None

            res = session.get(
                url="https://hdbits.org/ajax/tvdb.php",
                params={
                    "action": "parsename",
                    "title": path.name,
                    "uid": int(time.time() * 1000),
                },
            ).json()
            print(res)
            if not (tvdb := res.get("tvdb_id")):
                r = session.get(
                    url="https://hdbits.org/ajax/tvdb.php",
                    params={
                        "action": "showsearch",
                        "search": res["showname"],
                        "uid": int(time.time() * 1000),
                    },
                )
                r.raise_for_status()
                res2 = r.json()
                tvdb = next(iter(res2.keys()))
            tvdb = tvdb or input("Enter TVDB ID: ")

            season = res["season"]
            episode = res["episode"]
        else:
            imdb = input("Enter IMDb URL: ")
            tvdb = None
            season = None
            episode = None

        if re.search(r"\b(?:[hx]\.?264|avc)\b", str(path), flags=re.I):
            codec = "H.264"
        elif re.search(r"\b(?:[hx]\.?265|hevc)\b", str(path), flags=re.I):
            codec = "HEVC"
        elif re.search(r"\b(?:mp(?:eg)?-?2)\b", str(path), flags=re.I):
            codec = "MPEG-2"
        elif re.search(r"\b(?:vc-?1)\b", str(path), flags=re.I):
            codec = "VC-1"
        elif re.search(r"\b(?:vp-?9)\b", str(path), flags=re.I):
            codec = "VP9"
        elif re.search(r"\b(?:divx|xvid|[hx]\.?263)\b", str(path), flags=re.I):
            codec = "XviD"
        else:
            print("[red][bold]ERROR[/bold]: Unable to determine video codec[/red]")
            sys.exit(1)
        print(f"Detected codec as [bold][cyan]{codec}[/cyan][/bold]")

        if re.search(r"\b(?:b[dr]-?rip|blu-?ray|hd-?dvd)\b", str(path), flags=re.I):
            medium = "Blu-ray/HD-DVD"
        elif re.search(r"\b[ph]dtv\b|\.ts$", str(path), flags=re.I):
            medium = "Capture"
        elif re.search(r"\bweb-?rip\b", str(path), flags=re.I):  # TODO: Detect more encodes
            medium = "Encode"
        elif re.search(r"\bremux\b", str(path), flags=re.I):
            medium = "Remux"
        elif re.search(r"\bweb(?:-?dl)?\b", str(path), flags=re.I):
            medium = "WEB-DL"
        else:
            print("[red][bold]ERROR[/bold]: Unable to determine medium[/red]")
            sys.exit(1)
        print(f"Detected medium as [bold][cyan]{medium}[/cyan][/bold]")

        torrent_path = Path(f"{path}_files/{path.name}[HDB].torrent")

        data = {
            "name": path.name,
            "category": self.CATEGORY_MAP[category],
            "codec": self.CODEC_MAP[codec],
            "medium": self.MEDIUM_MAP[medium],
            "origin": 0,  # TODO: Support internal
            "descr": thumbnails,
            "techinfo": mediainfo,
            "imdb": imdb,
            "tvdb": tvdb,
            "tvdb_season": season,
            "tvdb_episode": episode,
            "anidb_id": None,  # TODO
        }
        print(data)

        if not auto:
            print("Press Enter to upload")
            input()

        res = session.post(
            url="https://hdbits.org/upload/upload",
            files={
                "file": (torrent_path.name, torrent_path.open("rb"), "application/x-bittorrent"),
            },
            data=data,
        ).text
        soup = BeautifulSoup(res, "lxml-html")
        torrent_url = f'https://hdbits.org{soup.select_one(".js-download")["href"]}'
        torrent_path.write_bytes(session.get(torrent_url).content)
