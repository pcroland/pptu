import re
import sys
import time

from bs4 import BeautifulSoup
from guessit import guessit
from imdb import Cinemagoer
from rich import print

from pymkt.uploaders import Uploader

ia = Cinemagoer()


class HDBitsUploader(Uploader):
    name = "HDBits"
    abbrev = "HDB"
    require_passkey = False

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
        if re.search(r"\.S\d+(E\d+)*\.", str(path)):
            print("Detected series")
            category = "TV"
        else:
            print("Detected movie")
            category = "Movie"

        if category == "TV":
            imdb = None

            res = self.session.get(
                url="https://hdbits.org/ajax/tvdb.php",
                params={
                    "action": "parsename",
                    "title": path.name,
                    "uid": int(time.time() * 1000),
                },
            ).json()
            print(res)
            if not (tvdb := res.get("tvdb_id")):
                r = self.session.get(
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
            imdb = None
            if (m := re.search(r"(.+?)\.S\d+(?:E\d+|\.)", path.name)) or (m := re.search(r"(.+?\.\d{4})\.", path.name)):
                title = re.sub(r" (\d{4})$", r" (\1)", m.group(1).replace(".", " "))
                print(f"Detected title: [bold][cyan]{title}[/cyan][/bold]")

                if imdb_results := ia.search_movie(title):
                    imdb = f"https://www.imdb.com/title/tt{imdb_results[0].movieID}/"
            else:
                print("[yellow][bold]WARNING[/bold]: Unable to extract title from filename[/yellow]")
            imdb = imdb or input("Enter IMDb URL: ")
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

        torrent_path = self.dirs.user_cache_path / f"{path.name}_files" / f"{path.name}[HDB].torrent"

        gi = guessit(path.name)
        name = path.name
        if gi.get("episode_details") != "Special":
            # Strip episode title
            name = name.replace(gi.get("episode_title", "").replace(" ", "."), "").replace("..", ".")
        # Strip streaming service
        name = re.sub(r"(\d+p)\.[a-z0-9]+\.(web)", r"\1.\2", name, flags=re.IGNORECASE)

        thumbnails_str = ""
        r = self.session.post(
            url="https://img.hdbits.org/upload_api.php",
            files={
                "username": self.config.get(self, "username"),
                "passkey": self.config.get(self, "passkey"),
                **{f"images_files[{i}]": open(snap, "rb") for i, snap in enumerate(snapshots)},
            },
            timeout=60,
        )
        r.raise_for_status()
        res = r.text
        for i, url in enumerate(res.split()):
            thumbnails_str += url
            if i % 2 == 0:
                thumbnails_str += " "
            else:
                thumbnails_str += "\n"

        data = {
            "name": name,
            "category": self.CATEGORY_MAP[category],
            "codec": self.CODEC_MAP[codec],
            "medium": self.MEDIUM_MAP[medium],
            "origin": 0,  # TODO: Support internal
            "descr": thumbnails_str,
            "techinfo": mediainfo,
            "imdb": imdb,
            "tvdb": tvdb,
            "tvdb_season": 0 if gi.get("episode_details") == "Special" else season,
            "tvdb_episode": episode,  # TODO: Get special episode number from TVDB
            "anidb_id": None,  # TODO
        }
        print(data)

        if not auto:
            print("Press Enter to upload")
            input()

        res = self.session.post(
            url="https://hdbits.org/upload/upload",
            files={
                "file": (torrent_path.name.replace("[HDB]", ""), torrent_path.open("rb"), "application/x-bittorrent"),
            },
            data=data,
        ).text
        soup = BeautifulSoup(res, "lxml-html")
        torrent_url = f'https://hdbits.org{soup.select_one(".js-download")["href"]}'
        torrent_path.write_bytes(self.session.get(torrent_url).content)

        # HDB requires redownloading the torrent as it includes a random unpredictable hash in each upload
        return torrent_path
