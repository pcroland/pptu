import re
import sys
import uuid
from http.cookiejar import MozillaCookieJar
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from platformdirs import PlatformDirs
from requests.adapters import HTTPAdapter, Retry
from rich import print
from ruamel.yaml import YAML

from pymkt.uploaders import Uploader


class AvZUploader(Uploader):
    COLLECTION_MAP = {
        "episode": 1,
        "season": 2,
        "series": 3,
    }

    def upload(self, path, mediainfo, snapshots, thumbnails, *, auto):
        dirs = PlatformDirs(appname="pymkt", appauthor=False)

        config = YAML().load(dirs.user_config_path / "config.yml")

        jar = MozillaCookieJar(dirs.user_data_path / "cookies" / "avz.txt")
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
                "all": config.get("proxy", {}).get("avz"),
            },
        )

        if re.search(r"\.S\d+(E\d+)+\.", str(path)):
            print("Detected episode")
            collection = "episode"
        elif re.search(r"\.S\d+\.", str(path)):
            print("Detected season")
            collection = "season"
        elif re.search(r"\.S\d+-S?\d+\.", str(path)):
            collection = "series"
        else:
            print("[red][bold]ERROR[/bold]: Movies are not yet supported[/red]")
            sys.exit(1)

        if (m := re.search(r"(.+?)\.S\d+(?:E\d+|\.)", path.name)) or (m := re.search(r"(.+?\.\d{4})\.", path.name)):
            title = m.group(1).replace(".", " ")
            print(f"Detected title: [bold][cyan]{title}[/cyan][/bold]")
        else:
            print("[red][bold]ERROR[/bold]: Unable to extract title from filename[/red]")
            sys.exit(1)

        if m := re.search(r"\.S(\d+)[E.]", path.name):
            season = int(m.group(1))
        else:
            print("[red][bold]ERROR[/bold]: Unable to extract season from filename[/red]")

        if m := re.search(r"\.S\d+E(\d+)\.", path.name):
            episode = int(m.group(1))
        else:
            episode = None

        res = session.get(url="https://avistaz.to/", timeout=60).text
        soup = BeautifulSoup(res, "lxml-html")
        token = soup.select_one('meta[name="_token"]')["content"]

        r = session.get(
            url="https://avistaz.to/ajax/movies/2",
            params={
                "term": title,
            },
            headers={
                "x-requested-with": "XMLHttpRequest",
            },
            timeout=60,
        )
        print(r)
        res = r.json()
        print(res)
        r.raise_for_status()
        res = res["data"][0]
        movie_id = res["id"]
        print(
            f'Found title: [bold][cyan]{res["title"]}[/cyan][/bold] ([bold][green]{res["release_year"]}[/green][/bold])'
        )
        data = {
            "_token": token,
            "type_id": 2,
            "movie_id": movie_id,
            "media_info": mediainfo,
        }
        print({**data, "_token": "[hidden]", "media_info": "[hidden]"})

        if not auto:
            print("Press Enter to continue")
            input()

        torrent_path = Path(f"{path}_files/{path.name}[AvZ].torrent")
        r = session.post(
            url="https://avistaz.to/upload/tv",
            data=data,
            files={
                "torrent_file": (torrent_path.name, torrent_path.open("rb"), "application/x-bittorrent"),
            },
            timeout=60,
        )
        upload_url = r.url
        res = r.text
        soup = BeautifulSoup(res, "lxml-html")
        print(soup.prettify())

        images = []
        for i in ("01", "02", "03"):
            img = Path(f"{path}_files/{i}.png")
            r = session.post(
                url="https://avistaz.to/ajax/image/upload",
                data={
                    "_token": token,
                    "qquuid": str(uuid.uuid4()),
                    "qqfilename": img.name,
                    "qqtotalfilesize": img.stat().st_size,
                },
                files={
                    "qqfile": (img.name, img.open("rb"), "image/png"),
                },
                headers={
                    "x-requested-with": "XMLHttpRequest",
                },
                timeout=60,
            )
            print(r)
            res = r.json()
            print(res)
            r.raise_for_status()
            images.append(res["imageId"])

        data = {
            "_token": token,
            "info_hash": soup.select_one('input[name="info_hash"]')["value"],
            "torrent_id": "",
            "type_id": 2,
            "task_id": upload_url.split("/")[-1],
            "file_name": (
                (path.stem if path.is_file() else path.name)
                .replace(".", " ")
                .replace("H 264", "H.264")
                .replace("H 265", "H.265")
                .replace("2 0 ", "2.0 ")
                .replace("5 1 ", "5.1 ")
            ),
            "anon_upload": 1,
            "description": "",
            "qqfile": "",
            "screenshots[]": images,
            "rip_type_id": soup.select_one('select[name="rip_type_id"] option[selected]')["value"],
            "video_quality_id": soup.select_one('select[name="video_quality_id"] option[selected]')["value"],
            "video_resolution": soup.select_one('input[name="video_resolution"]')["value"],
            "movie_id": movie_id,
            "tv_collection": self.COLLECTION_MAP[collection],
            "tv_season": season,
            "tv_episode": episode,
            "languages[]": [x["value"] for x in soup.select('select[name="languages[]"] option[selected]')],
            "subtitles[]": [x["value"] for x in soup.select('select[name="subtitles[]"] option[selected]')],
            "media_info": mediainfo,
        }
        print(data)

        if not auto:
            print("Press Enter to upload")
            input()

        r = session.post(url=upload_url, data=data, timeout=60)
        print(r)
        res = r.text
        soup = BeautifulSoup(res, "lxml-html")
        print(soup.prettify())
        r.raise_for_status()
        torrent_url = soup.select_one('a[href*="/download/"]')["href"]
        session.get(torrent_url, timeout=60)
