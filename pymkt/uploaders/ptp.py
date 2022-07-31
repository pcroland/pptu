import re
from http.cookiejar import MozillaCookieJar
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from imdb import Cinemagoer
from platformdirs import PlatformDirs
from requests.adapters import HTTPAdapter, Retry
from rich import print
from ruamel.yaml import YAML

from pymkt.uploaders import Uploader

ia = Cinemagoer()


class PTPUploader(Uploader):
    def upload(self, path, mediainfo, snapshots, thumbnails, *, auto):
        dirs = PlatformDirs(appname="pymkt", appauthor=False)

        config = YAML().load(dirs.user_config_path / "config.yml")

        jar = MozillaCookieJar(dirs.user_data_path / "cookies" / "ptp.txt")
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
                "all": config.get("proxy", {}).get("ptp"),
            },
        )

        imdb = None
        if (m := re.search(r"(.+?)\.S\d+(?:E\d+|\.)", path.name)) or (m := re.search(r"(.+?\.\d{4})\.", path.name)):
            title = m.group(1).replace(".", " ")
            print(f"Detected title: [bold][cyan]{title}[/cyan][/bold]")

            if imdb_results := ia.search_movie(title):
                imdb = f"https://www.imdb.com/title/tt{imdb_results[0].movieID}/"
        else:
            print("[yellow][bold]WARNING[/bold]: Unable to extract title from filename[/yellow]")
        imdb = imdb or input("Enter IMDb URL: ")

        imdb_movie = ia.get_movie(re.search(r"tt(\d+)", imdb).group(1))
        title = imdb_movie.data["original title"]
        year = imdb_movie.data["year"]

        print(f"IMDb: [cyan][bold]{title}[/bold] ({year})[/cyan]")

        groupid = None
        res = session.get(
            url="https://passthepopcorn.me/ajax.php",
            params={
                "action": "torrent_info",
                "imdb": imdb,
                "fast": "1",
            },
        ).json()
        print(res)
        if res:
            groupid = res[0]["groupid"]

        torrent_path = Path(f"{path}_files/{path.name}[PTP].torrent")

        if groupid:
            res = session.get(
                url="https://passthepopcorn.me/upload.php",
                params={
                    "groupid": groupid,
                },
            ).text
            soup = BeautifulSoup(res, "lxml-html")

            data = {
                "AntiCsrfToken": soup.select_one("#upload")["data-AntiCsrfToken"],
                "groupid": groupid,
                "type": "Feature Film",
                "remaster_title": "",
                "remaster_year": "",
                "internalrip": "on",  # TODO: Allow customizing this
                "source": "WEB",  # TODO: Auto-detect this instead of hardcoding
                "other_source": "",
                "codec": "* Auto-detect",
                "container": "* Auto-detect",
                "resolution": "* Auto-detect",
                "other_resolution_width": "",
                "other_resolution_height": "",
                "release_desc": "[mi]\n{mediainfo}\n[/mi]\n{snapshots}".format(
                    mediainfo=mediainfo, snapshots="\n".join(snapshots)
                ),
                "subtitles[]": [],  # TODO
                "nfo_text": "",
                "trumpable[]": [],  # No English Subtitles = 14
                "uploadtoken": "",
            }
            print(data)

            if not auto:
                print("Press Enter to upload")
                input()

            session.post(
                url="https://passthepopcorn.me/upload.php",
                params={
                    "groupid": groupid,
                },
                data={
                    "AntiCsrfToken": soup.select_one("#upload")["data-AntiCsrfToken"],
                    "groupid": groupid,
                    "type": "Feature Film",
                    "remaster_title": "",
                    "remaster_year": "",
                    "internalrip": "on",  # TODO: Allow customizing this
                    "source": "WEB",  # TODO: Auto-detect this instead of hardcoding
                    "other_source": "",
                    "codec": "* Auto-detect",
                    "container": "* Auto-detect",
                    "resolution": "* Auto-detect",
                    "other_resolution_width": "",
                    "other_resolution_height": "",
                    "release_desc": "[mi]\n{mediainfo}\n[/mi]\n{snapshots}".format(
                        mediainfo=mediainfo, snapshots="\n".join(snapshots)
                    ),
                    "subtitles[]": [],  # TODO
                    "nfo_text": "",
                    "trumpable[]": [],  # No English Subtitles = 14
                    "uploadtoken": "",
                },
                files={
                    "file": (torrent_path.name, torrent_path.open("rb"), "application/x-bittorrent"),
                },
            )
        else:
            print("[red][bold]ERROR[/bold]: Uploading new titles is not implemented yet")
