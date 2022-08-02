import json
import re
import subprocess
import sys

from bs4 import BeautifulSoup
from langcodes import Language
from rich import print

from pymkt.uploaders import Uploader


class BroadcasTheNetUploader(Uploader):
    COUNTRY_MAP = {
        "AD": 65,
        "AF": 51,
        "AG": 86,
        "AL": 62,
        "AN": 68,
        "AO": 33,
        "AR": 19,
        "AT": 34,
        "AU": 20,
        "BA": 64,
        "BB": 82,
        "BD": 83,
        "BE": 16,
        "BF": 57,
        "BG": 100,
        "BN": 113,
        "BR": 18,
        "BS": 79,
        "BZ": 31,
        "CA": 5,
        "CD": 50,
        "CH": 54,
        "CL": 48,
        "CN": 8,
        "CO": 95,
        "CR": 98,
        "CU": 49,
        "CZ": 43,
        "DE": 7,
        "DK": 10,
        "DO": 38,
        "DZ": 32,
        "EC": 78,
        "EE": 94,
        "EG": 99,
        "ES": 22,
        "FI": 4,
        "FJ": 102,
        "FR": 6,
        "GB": 12,
        "GR": 39,
        "GT": 40,
        "HK": 30,
        "HN": 76,
        "HR": 93,
        "HU": 71,
        "IL": 41,
        "IS": 13,
        "IT": 9,
        "JM": 28,
        "JP": 17,
        "KG": 77,
        "KH": 81,
        "KI": 55,
        "KP": 92,
        "KR": 27,
        "KW": 104,
        "LA": 84,
        "LB": 96,
        "LK": 105,
        "LT": 66,
        "LU": 29,
        "LV": 97,
        "MK": 103,
        "MX": 24,
        "MY": 37,
        "NG": 58,
        "NL": 15,
        "NO": 11,
        "NR": 60,
        "NZ": 21,
        "PE": 80,
        "PH": 56,
        "PK": 42,
        "PL": 14,
        "PR": 47,
        "PT": 23,
        "PY": 87,
        "RO": 72,
        "RS": 44,
        "RU": 3,
        "SA": 108,
        "SC": 45,
        "SE": 1,
        "SG": 25,
        "SK": 110,
        "SN": 90,
        "SU": 88,
        "TG": 91,
        "TM": 64,
        "TR": 52,
        "TT": 75,
        "TW": 46,
        "UA": 69,
        "US": 2,
        "UY": 85,
        "UZ": 53,
        "VE": 70,
        "VN": 74,
        "VU": 73,
        "WS": 36,
        "YU": 35,
        "ZA": 26,
    }

    def upload(self, path, mediainfo, snapshots, thumbnails, *, auto):
        if re.search(r"\.S\d+(E\d+)+\.", str(path)):
            print("Detected episode")
            type_ = "Episode"
        elif re.search(r"\.S\d+\.", str(path)):
            print("Detected season")
            type_ = "Season"
        else:
            print("[red][bold]ERROR[/bold]: Movies are not yet supported[/red]")
            sys.exit(1)

        release_name = path.stem if path.is_file() else path.name

        r = self.session.post(
            url="https://broadcasthe.net/upload.php",
            data={
                "type": type_,
                "scene_yesno": "yes",
                "autofill": release_name,
                "tvdb": "Get Info",
            },
            timeout=60,
        )
        soup = BeautifulSoup(r.text, "lxml-html")
        if r.status_code == 302:
            print("[red][bold]ERROR[/bold]: Cookies expired[/red]")
            sys.exit(1)
        if r.status_code != 200:
            print(f"[red][bold]ERROR[/bold]: HTTP Error {r.status_code}[/red]")
            print(soup.prettify())
            sys.exit(1)

        artist = soup.select_one('[name="artist"]').get("value")
        title = soup.select_one('[name="title"]').get("value")

        if artist == "AutoFill Fail" or title == "AutoFill Fail":
            print("[red][bold]ERROR[/bold]: AutoFill Fail[/red]")
            sys.exit(1)
        else:
            print("AutoFill complete")

        if path.is_dir():
            file = list(sorted([*path.glob("*.mkv"), *path.glob("*.mp4")]))[0]
        else:
            file = path
        if file.suffix == ".mkv":
            info = json.loads(subprocess.run(["mkvmerge", "-J", file], capture_output=True, encoding="utf-8").stdout)
            audio = next(x for x in info["tracks"] if x["type"] == "audio")
            lang = audio["properties"].get("language_ietf") or audio["properties"].get("language")
            if not lang:
                print("[red][bold]ERROR[/bold]: Unable to determine audio language[/red]")
                sys.exit(1)
            lang = Language.get(lang).fill_likely_values()
        else:
            print("[red][bold]ERROR[/bold]: MP4 is not yet supported[/red]")  # TODO

        print(f"Detected language as {lang.language}")
        print(f"Detected country as {lang.territory}")

        print(soup.prettify())

        data = {
            "submit": "true",
            "type": type_,
            "scenename": release_name,
            "seriesid": (soup.select_one('[name="seriesid"]') or {}).get("value"),
            "artist": artist,
            "title": title,
            "actors": soup.select_one('[name="actors"]').get("value"),
            "origin": "P2P",
            "foreign": None if lang.language == "en" else "on",
            "country": self.COUNTRY_MAP.get(lang.territory),
            "year": soup.select_one('[name="year"]').get("value"),
            "tags": soup.select_one('[name="tags"]').get("value"),
            "image": soup.select_one('[name="image"]').get("value"),
            "album_desc": soup.select_one('[name="album_desc"]').text,
            "fasttorrent": "on",
            "format": soup.select_one('[name="format"] [selected]').get("value"),
            "bitrate": soup.select_one('[name="bitrate"] [selected]').get("value"),
            "media": soup.select_one('[name="media"] [selected]').get("value"),
            "resolution": soup.select_one('[name="resolution"] [selected]').get("value"),
            "release_desc": f"{mediainfo}\n\n{thumbnails}",
            "tvdb": "autofilled",
        }
        print(data)

        if not auto:
            print("Press Enter to upload")
            input()

        torrent_path = self.dirs.user_cache_dir / f"{path}_files" / f"{path.name}[BTN].torrent"
        r = self.session.post(
            url="https://broadcasthe.net/upload.php",
            data=data,
            files={
                "file_input": (str(torrent_path), torrent_path.open("rb"), "application/x-bittorrent"),
            },
            timeout=60,
        )
