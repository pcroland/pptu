import hashlib
import re
import sys
import time

from guessit import guessit
from imdb import Cinemagoer
from pyotp import TOTP
from rich import print
from rich.prompt import Confirm

from ..utils import eprint, load_html, wprint
from . import Uploader


ia = Cinemagoer()


class HDBitsUploader(Uploader):
    name = "HDBits"
    abbrev = "HDB"
    require_passkey = False
    min_snapshots = 4  # 2 for movies and single episodes

    CAPTCHA_MAP = {
        "efe8518424149278ddfaaf609b6a0b1a4749f61b61ef28824da67d68fb333af3": "bug",
        "efa72724b28ccc386cc5c1384ea68ecd51ff9c7f7351dae908853aba40230ed1": "clock",
        "d462f4dde17c39168868373f8a2733f7e373ca89a471eb4ea247c55f096f0d7e": "flag",
        "4cee2b7c0807bf5301bb1c5ac89b160eac7b2b36d3ec88cfc4fb592146731654": "heart",
        "33a0bcf45bf94fa6e157310f4d99193a011b4287629c9a95cde49910741b164b": "house",
        "4e1a3fd65b3e7434429b9a207ecb7f1e357c2e0b46c081cf85533f7a419f5710": "key",
        "755c605d2d5b87dcc9d77e7640cdcbf10662f375e9294694e046dddb99a19474": "light bulb",
        "d38add46e8860bbb7e3ff577d0dfcad301dd68e23429e26e1447c31dc50d6ca2": "musical note",
        "8ef0ee9ba6b93a1dd5b1dbda7e24510d130cafb9a3453c2be710d09474274a5e": "pen",
        "518eb4eb8aaea5916d14531b479f046a0f1323fd0dbb2a9325b45a65715b9084": "world",
    }
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
    TAG_MAP = {
        "Amazon": r"\bAMZN\b",
        "Apple TV+": r"\bATVP\b",
        "BBC iPlayer": r"\biP\b",
        "Bravia Core": r"\bB?CORE\b",
        "Crackle": r"\bCRKL\b",
        "Crunchyroll": r"\bCR\b",
        "Disney+": r"\bDSNP\b",
        "Dolby Atmos": r"\b(?:Atmos|DDPA|TrueHDA)\b",
        "Dolby Vision": r"\b(?:DV|DoVi)\b",
        "Funimation": r"\bFUNI\b",
        "Hallmark Channel": r"\bHLMK\b",
        "HBO Max": r"\bHMAX\b",
        "HDR10": r"\bHDR",
        "HDR10+": r"(?i)\bHDR10(?:\+|P(?:lus)?)\b",
        "HFR": r"\bHFR\b",
        "HLG": r"\bHLG\b",
        "Hotstar": r"\bHS\b",
        "Hulu": r"\bHULU\b",
        "IMAX": r"\bIMAX\b",
        "iTunes": r"\biT\b",
        "Movies Anywhere": r"\bMA\.WEB\b",
        "Netflix": r"\bNF\b",
        "Open Matte": r"\bOM\b",
        "Paramount+": r"\bPMTP\b",
        "Peacock": r"\bPCOK\b",
        "Showtime": r"\bSHO\b",
        "Stan": r"\bSTAN\b",
    }

    def login(self):
        r = self.session.get("https://hdbits.org")
        if not r.url.startswith("https://hdbits.org/login"):
            return True

        wprint("Cookies missing or expired, logging in...")

        captcha = self.session.get("https://hdbits.org/simpleCaptcha.php", params={"numImages": "5"}).json()
        correct_hash = None
        for image in captcha["images"]:
            res = self.session.get("https://hdbits.org/simpleCaptcha.php", params={"hash": image}).content
            if self.CAPTCHA_MAP.get(hashlib.sha256(res).hexdigest()) == captcha["text"]:
                correct_hash = image
                print(f"Found captcha solution: [bold cyan]{captcha['text']}[/bold cyan] ([cyan]{correct_hash}[/cyan])")
                break
        if not correct_hash:
            print("[bold][red]ERROR[/red]: Unable to solve captcha, perhaps it has new images?")
            return False

        res = self.session.get("https://hdbits.org/login", params={"returnto": "/"}).text
        soup = load_html(res)

        totp_secret = self.config.get(self, "totp_secret")

        r = self.session.post(
            url="https://hdbits.org/login/doLogin",
            data={
                "csrf": soup.select_one("[name='csrf']")["value"],
                "uname": self.config.get(self, "username"),
                "password": self.config.get(self, "password"),
                "twostep_code": TOTP(totp_secret).now() if totp_secret else None,
            },
        )
        if "error=7" in r.url:
            r = self.session.post(
                url="https://hdbits.org/login/doLogin",
                data={
                    "csrf": soup.select_one("[name='csrf']")["value"],
                    "uname": self.config.get(self, "username"),
                    "password": self.config.get(self, "password"),
                    "twostep_code": Confirm.ask("Enter 2FA code: ")
                },
            )

        if "error" in r.url:
            soup = load_html(r.text)
            error = re.sub(r"\s+", " ", soup.select_one(".embedded").text).strip()
            eprint(error)
            return False

        return True

    @property
    def passkey(self):
        res = self.session.get("https://hdbits.org/").text
        return re.search(r"passkey=([a-f0-9]+)", res).group(1)

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
                wprint("Unable to extract title from filename.")
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

        name = path.name

        tags = []
        for tag, pattern in self.TAG_MAP.items():
            if re.search(pattern, name):
                tags.append(tag)

        gi = guessit(path.name)
        if gi.get("episode_details") != "Special":
            # Strip episode title
            name = name.replace(gi.get("episode_title", "").replace(" ", "."), "").replace("..", ".")
        # Strip streaming service
        name = re.sub(r"(\d+p)\.[a-z0-9]+\.(web)", r"\1.\2", name, flags=re.IGNORECASE)
        # DV/HDR normalization
        name = re.sub(r"HDR10(?:\+|P|Plus)", "HDR", name, flags=re.IGNORECASE)
        name = re.sub(r"(?:DV|DoVi)\.HDR", "DoVi", name)

        thumbnail_row_width = max(900, self.config.get(self, "snapshot_row_width", 900))
        allowed_widths = [100, 150, 200, 250, 300, 350]
        thumbnail_width = (thumbnail_row_width / self.config.get(self, "snapshot_columns", 2) - 5)
        thumbnail_width = max(x for x in allowed_widths if x <= thumbnail_width)

        thumbnails_str = ""
        r = self.session.post(
            url="https://img.hdbits.org/upload_api.php",
            files={
                **{f"images_files[{i}]": open(snap, "rb") for i, snap in enumerate(snapshots)},
                "thumbsize": f"w{thumbnail_width}",
                "galleryoption": "1",
                "galleryname": name,
            },
            timeout=60,
        )
        r.raise_for_status()
        res = r.text
        for i, url in enumerate(res.split()):
            thumbnails_str += url
            if i % self.config.get(self, "snapshot_columns", 2) == 0:
                thumbnails_str += " "
            else:
                thumbnails_str += "\n"

        data = {
            "name": name,
            "category": self.CATEGORY_MAP[category],
            "codec": self.CODEC_MAP[codec],
            "medium": self.MEDIUM_MAP[medium],
            "origin": 0,  # TODO: Support internal
            "descr": f"[center]{thumbnails_str}[/center]",
            "techinfo": mediainfo,
            "tags[]": tags,
            "imdb": imdb,
            "tvdb": tvdb,
            "tvdb_season": 0 if gi.get("episode_details") == "Special" else season,
            "tvdb_episode": episode,  # TODO: Get special episode number from TVDB
            "anidb_id": None,  # TODO
        }
        print(data)

        if not auto:
            if not Confirm.ask("\nUpload torrent?"):
                return False

        res = self.session.post(
            url="https://hdbits.org/upload/upload",
            files={
                "file": (torrent_path.name.replace("[HDB]", ""), torrent_path.open("rb"), "application/x-bittorrent"),
            },
            data=data,
        ).text
        soup = load_html(res)
        torrent_url = f'https://hdbits.org{soup.select_one(".js-download")["href"]}'
        torrent_path.write_bytes(self.session.get(torrent_url).content)

        return True
