from __future__ import annotations
from ast import arg

import json
import re
from typing import Optional, Union
from pathlib import Path
import requests

import httpx
from langcodes import Language
from guessit import guessit
from pymediainfo import MediaInfo
from imdb import Cinemagoer
from pyotp import TOTP
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    TaskProgressColumn,
    TextColumn,
    TimeRemainingColumn,
)
from rich.prompt import Prompt
from rich.status import Status

from ..utils import (
    eprint, generate_thumbnails, print, wprint, load_html, find, first_or_none, first
)
from . import Uploader


ia = Cinemagoer()


class nCoreUploader(Uploader):
    name: str = "nCore"
    abbrev: str = "nC"
    announce_url: list[str] = ["https://t.ncore.sh:2810/{passkey}/announce", "https://t.ncore.pro:2810/{passkey}/announce"]
    min_snapshots: int = 3
    snapshots_plus: int = 3
    exclude_regexs: str = r".*\.(ffindex|jpg|png|torrent|txt)$"
    source: Optional[str] = "ncore.pro"

    @property
    def passkey(self) -> Optional[str]:
        res = self.session.get("https://ncore.pro/torrents.php").text
        if m := find(r'<link rel="alternate" href="/rss.php\?key=([a-f0-9]+)" title', res):
            return m
        return None

    @property
    def get_unique(self) -> str:
        """
        This method sends a GET request to https://ncore.pro/ and extracts a unique ID from the response.
        The ID is returned as a string.
        """
        data = self.session.get(url="https://ncore.pro/").text
        id = find(
            r'<a href="exit.php\?q=(.*)" id="menu_11" class="menu_link">', data)

        return id if id else ""

    def keksh(self, file) -> Optional[str]:
        """
        Uploads a file to kek.sh and returns the URL of the uploaded file.
        """
        headers = dict()
        if self.config.get(self, "use_kek_api_key", True):
            headers = {
                #"x-kek-auth": "WOJCS1sFhuBbqejq.oc5ylmAowdXbD8Bvz,gxFA3Gpqs5laWoRMQZ"
            }

        res = self.client.post(
            url='https://kek.sh/api/v1/posts',
            headers=headers,
            files={
                'file': open(file, 'rb')
            }
        ).json()

        return f"https://i.kek.sh/{res['filename']}" if res.get('filename') else ""

    def link_shortener(self, url: Union[str, None]) -> Optional[str]:
        if url:
            url = url.replace("www.", "").replace("http://", "https://")

            if not url.startswith("https://"): url = f"https://{url}"

            if "imdb.com" in url:
                url = re.sub(r"(.+tt\d+)(.+)", r"\1", url)
                return url

            if "port.hu" in url:
                url = re.sub(r"(film/tv/)(.+?)(/)", r"\1x\3", url)
                return url

            if "mafab.hu" in url:
                url = re.sub(r"(/movies/)(.+?)(-[\d]+).+", r"\1x\3", url)
                return url

        return url

    def ajax_parser(self, value: str) -> str:
        """Parses the AJAX data for a given value."""
        m = find(rf'id="{value}" value="(.*)">', self.imdb_ajax_data)

        return m if m else ""

    def extract_nfo_urls(self, nfo: str) -> list[str]:
        """
        Extracts URLs from an NFO file and returns a list of URLs that belong to specific databases.
        """
        urls: list[str] = re.findall(r"https?://[^ ░▒▓█▄▌▐─│\n]+", nfo)
        self.databse_urls = [
            x for x in urls if any(
                database in x for database in
                {"imdb.com", "tvmaze.com", "thetvdb.com", "port.hu", "rottentomatoes.com", "myanimelist.net", "netflix.com", "mafab.hu"}
            )
        ]

        return self.databse_urls

    def mafab_scraper(self, imdb: str, gi: dict, urls: list, auto: bool) -> dict[str, Union[str, list[str]]]:
        """
        If NFO contains a Mafab link, it returns that. Otherwise, it tries to find the movie on Mafab.hu and returns the link.
        """
        urls.append("")
        mafab_link = first_or_none(x for x in urls if "mafab.hu" in x) or ""
        from_sec: bool = True if mafab_link else False
        data = dict()

        if not mafab_link:
            try:
                mafab_site: dict = self.client.get(
                    url=f"https://www.mafab.hu/js/autocomplete.php?v=20&term={gi['title'].replace(' ', '+')}",
                    headers={
                        "X-Requested-With": "XMLHttpRequest",
                    }
                ).json()
                for x in mafab_site:
                    if x["cat"] == "movie":
                        if (site := self.client.get(x["id"]).text) and str(imdb) in site:
                            mafab_link = x["id"]
                            data = self.mafab_data_scraper(site) or {}
                            break
            except Exception as e:
                wprint(f'error: {e}.')

        if not mafab_link:
            wprint("Mafab.hu scraping failed.")
            if not auto:
                mafab_link = Prompt.ask("Mafab.hu link: ")
            from_sec = True
        else:
            print(f"Mafab.hu link: {mafab_link}", True)
        if mafab_link and from_sec:
            data = self.mafab_data_scraper(self.client.get(mafab_link).text) or {}

        return {
            "link": mafab_link,
            **data
        }

    def port_scraper(self, imdb: str, gi: dict, urls: list, auto: bool) -> dict[str, Union[str, list[str]]]:
        """
        If NFO contains a Mafab link, it returns that. Otherwise, it tries to find the movie on Port.hu and returns the link.
        """
        urls.append("")
        port_link = first_or_none(x for x in urls if "port.hu" in x and "/-/" not in x) or ""
        from_sec: bool = True if port_link else False
        data = dict()

        if not port_link:
            try:
                port_site: dict = requests.get(
                    url=f"https://port.hu/search/suggest-list?q={gi['title'].replace(' ', '+')}",
                ).json()
                print(port_site)
                for x in port_site:
                    if (site := requests.get("https://port.hu" + x["url"]).text) and str(imdb) in site:
                        port_link = "https://port.hu" + x["url"]
                        data = self.port_data_scraper(site) or {}
                        temp = x.get("subtitle", "").split(",")
                        data["genre"] = (temp[0] or "").split(" ")
                        data["year"] = temp[-1]
                        break
            except Exception as e:
                wprint(f'error: {e}.')

        if not port_link:
            wprint("PORT.hu scraping failed.")
            if not auto:
                port_link = Prompt.ask("PORT.hu link: ")
            from_sec = True
        else:
            print(f"PORT.hu link: {port_link}", True)
        if port_link and from_sec:
            data = self.port_data_scraper(requests.get(port_link).text) or {}

        return {
            "link": port_link,
            **data
        }

    def mafab_data_scraper(self, site: str) -> dict[str, str]:
        """
        Extracts the description of a movie from Mafab.hu.
        """
        return_data = dict()

        soup = load_html(site)
        name = soup.find('meta', itemprop='name')
        if name and (name_ := find(r'<meta content="(.*)" itemprop="name"/>', str(name))):
            return_data["name"] = name_.strip()
        info = soup.find('div', class_='biobox_full_0') or soup.find('div', class_='bio-content biotab_0')
        if info and (info_ := info.find('p') or info.find('span')):
            return_data["info"] = info_.text
        point = soup.find('div', class_='mafab-votes filminfo-section-details-detail')     
        if point and (point_ := point.find('span', class_='dcontent bold')):
            return_data["point"] = point_.text.strip().strip(" szavazat").split(",")
            return_data["point"][0] = str(float(return_data["point"][0].strip("%")) / 10)
        genre = soup.find('meta', itemprop='description')
        if genre and (genre_ := find(r'<meta content="(.*)" itemprop="description"/>', str(genre))):
            return_data["genre"] = first(genre_.split(",")).split("|")
        year = soup.find('meta', itemprop='datePublished')
        if year and (year_ := find(r'<meta content="(.*)" itemprop="datePublished"/>', str(year))):
            return_data["year"] = year_[0:4]

        return return_data

    def port_data_scraper(self, site: str) -> dict[str, str]:
        """
        Extracts the description of a movie from Port.hu.
        """
        return_data = dict()
        soup = load_html(site)
        script = soup.find('script', type='application/ld+json')
        if script and (info_ := json.loads(script.string)):
            return_data["name"] = info_.get('name', "")
            return_data["info"] = info_.get('description', "")
            return_data["genre"] = info_.get('genre', "").split()
            rating = info_.get('aggregateRating', {})
            return_data["point"] = [rating.get('ratingValue', ""), rating.get('ratingCount', "")]
        name = find(r'<title>(.*)</title>', site)
        if name:
            return_data["name"] = name.strip()
        cat = soup.find('div', class_="summary")
        if cat and (cat_ := cat.find('span')):
            temp = cat_.text.split(",")
            return_data["year"] = temp[-1]
            return_data["genre"] = (temp[0] or "").split(" ")

        return return_data

    def login(self, *, auto: bool) -> bool:
        if self.config.get(self, "snapshots"):
            # set snapshots number from config
            self.min_snapshots += self.config.get(self, "snapshot_columns", 2) \
                                * self.config.get(self, "snapshot_rows", 3)

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
            eprint("Failed to login.", exit_code=1)

        return True

    def prepare(  # type: ignore[override]
        # In the `prepare` and `upload` methods of the `nCoreUploader` class, `self` refers to the
        # instance of the class itself, while `path` is a parameter that represents the file path of
        # the media file being prepared or uploaded.
        self, path: Path, torrent_path: Path, mediainfo: str, snapshots: list[Path], *, note: Optional[str], auto: bool
    ) -> bool:
        type_: str = ""
        urls = list()
        self.databse_urls = list()
        imdb_id: Optional[str] = None
        release_name = path.stem if path.is_file() else path.name
        gi: dict = guessit(path.name)
        self.client = httpx.Client(
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/119.0'"
            },
            transport=httpx.HTTPTransport(retries=5, proxy=self.config.get(self, "proxy")),
        )

        if re.search(r"\.S\d+(E\d+|\.Special)+\.", str(path)) or gi["type"] == "episode":
            print("Detected episode")
            type_ = "ser"
        elif re.search(r"\.S\d+\.", str(path)) or gi["type"] == "season":
            print("Detected season")
            type_ = "ser"
        else:
            print("Detected movie")
            type_ = ""

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
                title = re.sub(r" (\d{4})$", r" (\1)", m.group(1).replace(".", " "))

                if imdb_results := ia.search_movie(title):
                    imdb_id = imdb_results[0].movieID

        if not imdb_id:
            if auto:
                eprint("No IMDb ID specified in config")
                return False
            imdb_id = Prompt.ask("Enter IMDb ID: ")
            if not imdb_id:
                eprint("No IMDb ID specified")
                return False

        if imdb_id and "tt" not in imdb_id:
            imdb_id = f"tt{imdb_id}"

        self.imdb_ajax_data = self.session.get(
            url=f"https://ncore.pro/ajax.php?action=imdb_movie&imdb_movie={imdb_id.strip('tt')}",
        ).text

        if path.is_dir():
            file = sorted([*path.glob("*.mkv"), *path.glob("*.mp4")])[0]
        else:
            file = path
        with Status("[bold magenta]Parsing for info scraping...") as _:
            m_info_temp: str = MediaInfo.parse(file, output="JSON", full=True)
            if m_info_temp:
                mediainfo_: dict = json.loads(m_info_temp)["media"]["track"]
            else:
                eprint("MediaInfo parsing failed.", exit_code=1)

        video = first_or_none(x for x in mediainfo_ if x["@type"] == "Video")
        if video and (int(video["Height"]) < 720):
            type_ = "xvid" + type_
        else:
            type_ = "hd" + type_

        audios: set = (x for x in mediainfo_ if x["@type"] == "Audio")
        for num, audio in enumerate(audios, 1):
            lang = audio["Language"]
            if not lang:
                eprint(
                    f"Unable to determine {num} audio language.", exit_code=0)
                continue
            lang = Language.get(lang)
            if not lang.language:
                eprint("Primary audio track has no language set.")
            if "hu" in str(lang).lower() and (".HUN." in release_name or ".HUN-" in release_name):
                type_ += "_hun"
                break

        thumbnails_str: str = ""

        # if name is too long, put it in the description
        if len(release_name) > 83:
            thumbnails_str += f"[center][highlight][size=10pt]{release_name}[/size][/highlight][/center]\n\n\n"

        if snapshots[0:-3]:
            thumbnails_str += "[spoiler=Screenshots][center]"
            with Progress(
                TextColumn("[progress.description]{task.description}[/]"),
                BarColumn(),
                MofNCompleteColumn(),
                TaskProgressColumn(),
                TimeRemainingColumn(elapsed_when_finished=True),
            ) as progress:
                snapshot_urls = []
                for snap in progress.track(snapshots[0:-3], description="Uploading snapshots"):
                    snapshot_urls.append(self.keksh(snap))

            thumbnail_row_width = min(660, self.config.get(self, "snapshot_row_width", 660))
            thumbnail_width = (thumbnail_row_width / self.config.get(self, "snapshot_row", 3))
            thumbnail_urls = []
            thumbnails = generate_thumbnails(
                snapshots[0:-3], width=thumbnail_width, file_type="jpg")

            for thumb in progress.track(thumbnails, description="Uploading thumbnails"):
                thumbnail_urls.append(self.keksh(thumb))

            for i in range(len(snapshots) - 3):
                snap = snapshot_urls[i]
                thumb = thumbnail_urls[i]
                thumbnails_str += f"[url={snap}][img]{thumb}[/img][/url]"
                if i+1 % self.config.get(self, "snapshot_columns", 3) == 0:
                    thumbnails_str += "\n"
            thumbnails_str += "[i] (Kattints a képekre a teljes felbontásban való megtekintéshez.)[/i][/center][/spoiler]"

        description = f"{thumbnails_str or ''}"
        hun_name: str = ""
        year: str = ""
        database: str = ""
        if note:
            description = f"[quote]{note}[/quote]\n\n{description}"
        if config := self.config.get(self, "description"):
            if config == "mafab" or config is True:
                mafab: dict = self.mafab_scraper(imdb_id, gi, urls, auto)
                if (link := mafab.get("link")) and (info := mafab.get("info")):
                    description = f"[url={link}]Mafab.hu[/url]: {info}\n\n{description}"
                    database = link
                hun_name = mafab.get("name", "")
                year = mafab.get("year", "")
            elif config == "port" or config is True and "mafab" not in description:
                port: dict = self.port_scraper(imdb_id, gi, urls, auto)
                if (link := port.get("link")) and (info := port.get("info")):
                    description = f"[url={link}]PORT.hu[/url]: {info}\n\n{description}"
                    database = link
                hun_name = port.get("name", "")
                year = port.get("year", "")
        description = description.strip()

        self.data = {
            "getUnique": self.get_unique,
            "eredeti": "igen",
            "infobar_site": "imdb",
            "tipus": type_,
            "torrent_nev": release_name,
            "szoveg": description,
            "imdb_id": imdb_id,
            "film_adatbazis": self.link_shortener(next(x for x in self.databse_urls + [""] if "imdb.com" not in x) or database),
            "infobar_picture": self.ajax_parser("movie_picture"),
            "infobar_rank": self.ajax_parser("movie_rank"),
            "infobar_genres": self.ajax_parser("movie_genres"),
            "megjelent": self.ajax_parser("movie_megjelenes_eve") or year,
            "orszag": self.ajax_parser("movie_orszag"),
            "hossz": self.ajax_parser("movie_hossz"),
            "film_magyar_cim": self.ajax_parser("movie_magyar_cim") or hun_name,
            "film_angol_cim":  self.ajax_parser("movie_angol_cim"),
            "film_idegen_cim": self.ajax_parser("movie_magyar_cim") or hun_name,
            "rendezo": self.ajax_parser("movie_rendezo"),
            "szereplok": self.ajax_parser("movie_szereplok"),
            "szezon": "",
            "epizod_szamok": "",
            "keresre": "nem",
            # "keres_kodja": "$request_id", # TODO: implement
            "anonymous": self.config.get(self, "anonymous_upload", False),
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
                "kep1": (str(snapshots[-3]), snapshots[-3].open("rb"), "image/png"),
                "kep2": (str(snapshots[-2]), snapshots[-2].open("rb"), "image/png"),
                "kep3": (str(snapshots[-1]), snapshots[-1].open("rb"), "image/png"),
            },
            data=self.data,
        )

        if "A feltöltött torrent már létezik" in r.text:
            wprint("Torrent already exists.")
            return False
        elif "upload.php" in r.url:
            return False

        print(f"nCore link: {r.url.replace('/torrents.php?action=details&id=', '/t/')}", True)

        return True
