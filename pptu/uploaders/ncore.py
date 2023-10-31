from __future__ import annotations
import requests

import json
import re
import subprocess
from typing import Optional
from pathlib import Path

from guessit import guessit
from imdb import Cinemagoer
from langcodes import Language
from pyotp import TOTP
from rich.progress import BarColumn, MofNCompleteColumn, Progress, TaskProgressColumn, TextColumn, TimeRemainingColumn
from rich.prompt import Prompt

from ..utils import eprint, generate_thumbnails, print, wprint
from . import Uploader


ia = Cinemagoer()


class nCoreUploader(Uploader):
    name: str = "nCore"
    abbrev: str = "nC"
    announce_url: str = "http://t.ncore.sh:2710/announce"
    min_snapshots = 9
    exclude_regexs: str = r".*\.(ffindex|jpg|png|torrent|txt)$"

    def keksh(self, file) -> Optional[str]:
        """
        Uploads a file to kek.sh and returns the URL of the uploaded file.
        """
        files = {'file': open(file, 'rb')}
        res: dict = requests.post(
            url='https://kek.sh/api/v1/posts',
            files=files
        ).json()

        return f"https://i.kek.sh/{res['filename']}" if res.get('filename') else ""

    def get_unique(self) -> str:
        """
        This method sends a GET request to https://ncore.pro/ and extracts a unique ID from the response.
        The ID is returned as a string.
        """
        data = self.session.get(url=f"https://ncore.pro/").text
        id = re.search(
            r'<a href="exit.php\?q=(.*)" id="menu_11" class="menu_link">', data)

        return id.group(1) if id else ""

    def ajax_parser(self, value: str) -> str:
        """Parses the AJAX data for a given value."""
        m = re.findall(rf'id="{value}" value="(.*)"', self.imdb_ajax_data)

        return m[0] if m else ""

    def extract_nfo_urls(self, nfo: str) -> list[str]:
        """
        Extracts URLs from an NFO file and returns a list of URLs that belong to specific databases.
        """
        urls: list[str] = re.findall(r"https?://[^ ░▒▓█▄▌▐─│\n]+", nfo)
        self.databse_urls = [x for x in urls if any(database in x for database in \
        ["imdb.com", "tvmaze.com", "thetvdb.com", "port.hu", "rottentomatoes.com", "myanimelist.net", "netflix.com", "mafab.hu"])]

        return self.databse_urls

    def scrape_port(self, imdb: str, release_name: str) -> str:
        gi = guessit(release_name)
        print(gi['title'])
        port_link = requests.get(
            url=f"https://port.hu/search/suggest-list?q={gi['title'].replace(' ', '+')}",
        ).json()[0].get('url', '')
        print(f"Scraping port.hu for link: {port_link}")
        port_link = f"https://port.hu{port_link}"
        if "https://port.hu" == port_link:
            wprint('port.hu scraping failed.')
            port_link = Prompt.ask('port.hu link: ')
        port_link_content = requests.get(port_link).text
        if str(imdb) not in str(port_link_content):
            wprint('port.hu scraping failed.')
            port_link = Prompt.ask('port.hu link: ')

        return port_link

    def login(self, *, auto: bool) -> bool:

        r = self.session.get("https://ncore.pro/")
        if "login.php" not in r.url:
            return True

        wprint("Cookies missing or expired, logging in...")

        if not (username := self.config.get(self, "username")):
            eprint("No username specified in config, cannot log in.")
            return False

        if not (password := self.config.get(self, "password")):
            eprint("No password specified in config, cannot log in.")
            return False
        tfa_code = None

        if totp_secret := self.config.get(self, "totp_secret"):
            tfa_code = TOTP(totp_secret).now()
        else:
            if auto:
                eprint("No TOTP secret specified in config")
                return False
            tfa_code = Prompt.ask("Enter 2FA code")

        print("Logging in")
        r = self.session.post(
            url="https://ncore.pro/login.php?2fa",
            data={
                "set_lang": "hu",
                "submitted": "1",
                "nev": username,
                "pass": password,
                "2factor": tfa_code,
                "ne_leptessen_ki": "1",
            },
        )
        r.raise_for_status()

        r = self.session.get("https://ncore.pro/")
        if "login.php" in r.url:
            eprint("Failed to login.")
            return False

        return True

    def prepare(  # type: ignore[override]
        # In the `prepare` and `upload` methods of the `nCoreUploader` class, `self` refers to the
        # instance of the class itself, while `path` is a parameter that represents the file path of
        # the media file being prepared or uploaded.
        self, path: Path, torrent_path: Path, mediainfo: str, snapshots: list[Path], *, note: Optional[str], auto: bool
    ) -> bool:
        type_: str = ""
        if re.search(r"\.S\d+(E\d+|\.Special)+\.", str(path)):
            print("Detected episode")
            type_ = "ser"
        elif re.search(r"\.S\d+\.", str(path)):
            print("Detected season")
            type_ = "ser"
        else:
            print("Detected movie")
            type_ = ""

        release_name = path.stem if path.is_file() else path.name
        databases = list()
        imdb_id: Optional[str] = None
        if path.is_dir():
            self.nfo_file = sorted([*path.glob("*.nfo")])
            if self.nfo_file:
                self.nfo_file = self.nfo_file[0]
                urls = self.extract_nfo_urls(
                    Path(self.nfo_file).read_text(encoding="CP437", errors="ignore"))
                imdb_id = next((x.split("/")[-2]
                               for x in urls if "imdb.com" in x), None)
            else:
                self.nfo_file = Path(path/f"{release_name}.nfo")
                with self.nfo_file.open("w", encoding="ascii") as f:
                    f.write(mediainfo)
        if not imdb_id:
            if (m := re.search(r"(.+?)\.S\d+(?:E\d+|\.)", path.name)) or (m := re.search(r"(.+?\.\d{4})\.", path.name)):
                title = re.sub(r" (\d{4})$", r" (\1)",
                               m.group(1).replace(".", " "))

                if imdb_results := ia.search_movie(title):
                    imdb_id = imdb_results[0].movieID

        if not imdb_id:
            if auto:
                eprint("No IMDb ID specified in config")
                return False
            imdb_id = Prompt.ask("Enter IMDb ID")
            if not imdb_id:
                eprint("No IMDb ID specified")
                return False

        self.imdb_ajax_data = self.session.get(
            url=f"https://ncore.pro/ajax.php?action=imdb_movie&imdb_movie={imdb_id}",
        ).text

        if path.is_dir():
            file = sorted([*path.glob("*.mkv"), *path.glob("*.mp4")])[0]
        else:
            file = path
        if file.suffix == ".mkv":
            info = json.loads(subprocess.run(
                ["mkvmerge", "-J", file], capture_output=True, encoding="utf-8").stdout)
            video = next(x for x in info["tracks"] if x["type"] == "video")
            if q := video["properties"]["display_dimensions"].split("x"):
                if int(q[0]) < 720:
                    type_ = "xvid" + type_
                else:
                    type_ = "hd" + type_
            audios = (x for x in info["tracks"] if x["type"] == "audio")
            for num, audio in enumerate(audios, 1):
                lang = audio["properties"].get(
                    "language_ietf") or audio["properties"].get("language")
                if not lang:
                    eprint(
                        f"Unable to determine {num} audio language.", exit_code=0)
                    continue
                if "Hungarian" in lang and release_name in (".HUN.", ".HUN-"):
                    type_ += "_hun"
                    break
        elif file.suffix == ".mp4":
            eprint("MP4 is not yet supported.")  # TODO: use mediainfo
            return False
        else:
            eprint("File must be MKV or MP4.")
            return False

        thumbnails_str: str = ""

        # if name is too long
        if len(release_name) > 83:
            thumbnails_str += f"[center][highlight][size=10pt]{release_name}[/size][/highlight][/center]\n\n"

        thumbnails_str += "[spoiler=Screenshots][center]"
        with Progress(
            TextColumn("[progress.description]{task.description}[/]"),
            BarColumn(),
            MofNCompleteColumn(),
            TaskProgressColumn(),
            TimeRemainingColumn(elapsed_when_finished=True),
        ) as progress:
            snapshot_urls = []
            for snap in progress.track(snapshots, description="Uploading snapshots"):
                snapshot_urls.append(self.keksh(snap))

        thumbnail_row_width = min(530, self.config.get(
            self, "snapshot_row_width", 530))
        thumbnail_width = (thumbnail_row_width /
                           self.config.get(self, "snapshot_columns", 2)) - 5
        thumbnail_urls = []
        thumbnails = generate_thumbnails(snapshots[0:6], width=thumbnail_width)

        for thumb in progress.track(thumbnails, description="Uploading thumbnails"):
            thumbnail_urls.append(self.keksh(thumb))

        for i in range(len(snapshots) - 3):
            snap = snapshot_urls[i]
            thumb = thumbnail_urls[i]
            thumbnails_str += rf"[url={snap}][img]{thumb}[/img][/url]"
            if i % self.config.get(self, "snapshot_columns", 2) == 0:
                thumbnails_str += " "
            else:
                thumbnails_str += "\n"
        thumbnails_str += "[i]  (Kattints a képekre a teljes felbontásban való megtekintéshez.)[/i][/center][/spoiler]"

        description = f"{thumbnails_str}"
        if self.config.get(self, "port_description") and imdb_id:
            description = f"{self.scrape_port(imdb_id, release_name)}\n{description}"
        if note:
            description = f"[quote]{note}[/quote]\n{description}"
        description = description.strip()

        self.data = {
            "getUnique": self.get_unique(),
            "eredeti": "igen",
            "infobar_site": "imdb",
            "tipus": type_,
            "torrent_nev": release_name,
            "szoveg": description,
            "imdb_id": imdb_id,
            "film_adatbazis": next(x for x in self.databse_urls + [""] if "imdb.com" not in x),
            "infobar_picture": self.ajax_parser("movie_picture"),
            "infobar_rank": self.ajax_parser("movie_rank"),
            "infobar_genres": self.ajax_parser("movie_genres"),
            "megjelent": self.ajax_parser("movie_megjelenes_eve"),
            "orszag": self.ajax_parser("movie_orszag"),
            "hossz": self.ajax_parser("movie_hossz"),
            "film_magyar_cim": self.ajax_parser("movie_magyar_cim"),
            "film_angol_cim":  self.ajax_parser("movie_angol_cim"),
            "film_idegen_cim": self.ajax_parser("movie_magyar_cim"),
            "rendezo": self.ajax_parser("movie_rendezo"),
            "szereplok": self.ajax_parser("movie_szereplok"),
            "szezon": "",
            "epizod_szamok": "",
            "keresre": "nem",
            # "keres_kodja": "$request_id",
            "anonymous": self.config.get(self, "anonymous_upload"),
            "elrejt": "nem",
            "mindent_tud1": "szabalyzat",
            "mindent_tud3": "seedeles",
        }

        return True

    def upload(  # type: ignore[override]
        self, path: Path, torrent_path: Path, mediainfo: str, snapshots: list[Path], *, note: Optional[str], auto: bool
    ) -> bool:

        r = self.session.post(
            url="https://ncore.pro/upload.php",
            files={
                "torrent_fajl": (str(torrent_path), torrent_path.open("rb"), "application/x-bittorrent"),
                "nfo_fajl": (str(self.nfo_file), self.nfo_file.open("rb"), "application/octet-stream"),
                "kep1": (str(snapshots[6]), snapshots[6].open("rb"), "image/png"),
                "kep2": (str(snapshots[7]), snapshots[7].open("rb"), "image/png"),
                "kep3": (str(snapshots[8]), snapshots[8].open("rb"), "image/png"),
            },
            data=self.data,
        )

        if "A feltöltött torrent már létezik" in r.text:
            wprint("Torrent already exists.")
            return False
        elif "upload.php" in r.url:
            return False

        return True
