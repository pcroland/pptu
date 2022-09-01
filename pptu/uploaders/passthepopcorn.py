import os
import re

from imdb import Cinemagoer
from pymediainfo import MediaInfo
from pyotp import TOTP
from rich.markup import escape
from rich.prompt import Confirm, Prompt

from ..utils import eprint, load_html, rprint, wprint
from . import Uploader


ia = Cinemagoer()


class PassThePopcornUploader(Uploader):
    name = "PassThePopcorn"
    abbrev = "PTP"
    source = "PTP"
    announce_url = "http://please.passthepopcorn.me:2710/{passkey}/announce"
    min_snapshots = 3
    all_files = True

    def __init__(self):
        super().__init__()
        self.anti_csrf_token = None

    @property
    def passkey(self):
        res = self.session.get("https://passthepopcorn.me/upload.php").text
        soup = load_html(res)
        return soup.select_one("input[value$='/announce']")["value"].split("/")[-2]

    def login(self):
        r = self.session.get("https://passthepopcorn.me/user.php?action=edit", allow_redirects=False)
        if r.status_code == 200:
            return True

        wprint("Cookies missing or expired, logging in...")

        if not (username := self.config.get(self, "username")):
            eprint("No username specified in config, cannot log in.")
            return False

        if not (password := self.config.get(self, "password")):
            eprint("No password specified in config, cannot log in.")
            return False

        if not (passkey := self.config.get(self, "passkey")):
            eprint("No passkey specified in config, cannot log in.")
            return False

        totp_secret = self.config.get(self, "totp_secret")

        res = self.session.post(
            url="https://passthepopcorn.me/ajax.php?action=login",
            data={
                "Popcron": "",
                "username": username,
                "password": password,
                "passkey": passkey,
                "WhatsYourSecret": "Hacker! Do you really have nothing better to do than this?",
                "keeplogged": "1",
                **({
                    "TfaType": "normal",
                    "TfaCode": TOTP(totp_secret).now(),
                } if totp_secret else {}),
            },
        ).json()

        if res["Result"] == "TfaRequired":
            totp_code = Prompt.ask("Enter 2FA code")
            res = self.session.post(
                url="https://passthepopcorn.me/ajax.php?action=login",
                data={
                    "Popcron": "",
                    "username": username,
                    "password": password,
                    "passkey": passkey,
                    "WhatsYourSecret": "Hacker! Do you really have nothing better to do than this?",
                    "keeplogged": "1",
                    "TfaType": "normal",
                    "TfaCode": totp_code,
                },
            ).json()

        if res["Result"] != "Ok":
            eprint(f"Login failed: [cyan]{res['Result']}[/]")
            return False

        self.anti_csrf_token = res["AntiCsrfToken"]
        return True

    def prepare(self, path, mediainfo, snapshots, *, auto):
        imdb = None
        if (m := re.search(r"(.+?)\.S\d+(?:E\d+|\.)", path.name)) or (m := re.search(r"(.+?\.\d{4})\.", path.name)):
            title = re.sub(r" (\d{4})$", r" (\1)", m.group(1).replace(".", " "))
            rprint(f"Detected title: [bold cyan]{title}[/]")

            if imdb_results := ia.search_movie(title):
                imdb = f"https://www.imdb.com/title/tt{imdb_results[0].movieID}/"
        else:
            wprint("Unable to extract title from filename.")
        imdb = imdb or input("Enter IMDb URL: ")

        imdb_movie = ia.get_movie(re.search(r"tt(\d+)", imdb).group(1))
        title = imdb_movie.data["original title"]
        year = imdb_movie.data["year"]

        rprint(f"IMDb: [cyan][bold]{title}[/] [not bold]({year})[/][/]")

        self.groupid = None
        torrent_info = self.session.get(
            url="https://passthepopcorn.me/ajax.php",
            params={
                "action": "torrent_info",
                "imdb": imdb,
                "fast": "1",
            },
        ).json()[0]
        rprint(torrent_info, highlight=True)
        self.groupid = torrent_info.get("groupid")

        self.torrent_path = self.dirs.user_cache_path / f"{path.name}_files" / f"{path.name}[PTP].torrent"

        res = self.session.get("https://passthepopcorn.me/upload.php", params={"groupid": self.groupid}).text

        if not self.anti_csrf_token:
            soup = load_html(res)
            self.anti_csrf_token = soup.select_one("[name='AntiCsrfToken']")["value"]

        if path.is_dir():
            file = list(sorted([*path.glob("*.mkv"), *path.glob("*.mp4")]))[0]
        else:
            file = path
        mediainfo_obj = MediaInfo.parse(file)
        no_eng_subs = (
            all(not x.language.startswith("en") for x in mediainfo_obj.audio_tracks)
            and all(not x.language.startswith("en") for x in mediainfo_obj.text_tracks)
        )

        snapshot_urls = []
        for snap in snapshots:
            with open(snap, "rb") as fd:
                r = self.session.post(
                    url="https://ptpimg.me/upload.php",
                    files={
                        "file-upload[]": fd,
                    },
                    data={
                        "api_key": self.config.get(self, "ptpimg_api_key") or os.environ.get("PTPIMG_API_KEY"),
                    },
                    headers={
                        "Referer": "https://ptpimg.me/index.php",
                    },
                    timeout=60,
                )
                r.raise_for_status()
                res = r.json()
                snapshot_urls.append(f'https://ptpimg.me/{res[0]["code"]}.{res[0]["ext"]}')

        if re.search(r"\.S\d+\.", str(path)):
            rprint("Detected series")
            type_ = "Miniseries"
            desc = ""
            for i in range(len(mediainfo)):
                desc += "[mi]\n{mediainfo}\n[/mi]\n{snapshots}\n\n".format(
                    mediainfo=mediainfo[i],
                    snapshots=snapshot_urls[i],
                )
        else:
            # TODO: Detect other types
            rprint("Detected movie")
            type_ = "Feature Film"
            desc = "[mi]\n{mediainfo}\n[/mi]\n{snapshots}".format(
                mediainfo=mediainfo[0],
                snapshots="\n".join(snapshot_urls),
            )
        desc = desc.strip()

        if re.search(r"\b(?:b[dr]-?rip|blu-?ray)\b", str(path), flags=re.I):
            source = "Blu-ray"
        elif re.search(r"\bhd-?dvd\b", str(path), flags=re.I):
            source = "HD-DVD"
        elif re.search(r"\bdvd(?:rip)?\b", str(path), flags=re.I):
            source = "DVD"
        elif re.search(r"\bweb-?(?:dl|rip)?\b", str(path), flags=re.I):
            source = "WEB"
        elif re.search(r"\bhdtv\b", str(path), flags=re.I):
            source = "HDTV"
        elif re.search(r"\bpdtv\b|\.ts$", str(path), flags=re.I):
            source = "TV"
        elif re.search(r"\bvhs(?:rip)?\b", str(path), flags=re.I):
            source = "VHS"
        else:
            source = "Other"
        rprint(f"Detected source: [bold cyan]{source}[/]")

        self.data = {
            "AntiCsrfToken": soup.select_one("[name='AntiCsrfToken']")["value"],
            "type": type_,
            "imdb": imdb,
            "title": torrent_info.get("title"),
            "year": torrent_info.get("year"),
            "image": imdb_movie.data["cover url"],
            "remaster_title": "",
            "remaster_year": "",
            "internalrip": "on",  # TODO: Allow customizing this
            "source": source,
            "other_source": "",
            "codec": "* Auto-detect",
            "container": "* Auto-detect",
            "resolution": "* Auto-detect",
            "tags": imdb_movie.data["genres"],
            "other_resolution_width": "",
            "other_resolution_height": "",
            "release_desc": desc,
            "nfo_text": "",
            "trumpable[]": [14] if no_eng_subs else [],
            "uploadtoken": "",
            **res[0],
        }

        return True

    def upload(self, path, mediainfo, snapshots, *, auto):
        rprint(self.data, highlight=True)

        if not auto:
            if not Confirm.ask("\nUpload torrent?"):
                return False

        res = self.session.post(
            url="https://passthepopcorn.me/upload.php",
            params={
                "groupid": self.groupid,
            },
            data=self.data,
            files={
                "file_input": (self.torrent_path.name, self.torrent_path.open("rb"), "application/x-bittorrent"),
            },
        ).text
        soup = load_html(res)
        if error := soup.select_one(".alert--error"):
            eprint(escape(error.get_text()))
            return False

        return True
