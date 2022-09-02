import re
import time
import uuid
from abc import ABC

from pyotp import TOTP
from rich.markup import escape
from rich.prompt import Confirm, Prompt

from ..utils import eprint, load_html, print, wprint
from . import Uploader


class AvistaZNetworkUploader(Uploader, ABC):  # noqa: B024
    min_snapshots = 3

    COLLECTION_MAP = {
        "movie": None,
        "episode": 1,
        "season": 2,
        "series": 3,
    }

    @property
    def domain(self):
        return f"{self.name.lower()}.to"

    @property
    def base_url(self):
        return f"https://{self.domain}"

    @property
    def announce_url(self):
        return f"https://tracker.{self.domain}/{{passkey}}/announce"

    def login(self):
        r = self.session.get(f"{self.base_url}/account", allow_redirects=False, timeout=60)
        if r.status_code == 200:
            return True

        wprint("Cookies missing or expired, logging in...")

        if not (username := self.config.get(self, "username")):
            eprint("No username specified in config, cannot log in.")
            return False

        if not (password := self.config.get(self, "password")):
            eprint("No password specified in config, cannot log in.")
            return False

        totp_secret = self.config.get(self, "totp_secret")

        if not (twocaptcha_api_key := self.config.get(self, "2captcha_api_key")):
            eprint("No 2captcha_api_key specified in config, cannot log in.")
            return False

        attempt = 1
        done = False
        while not done:
            res = self.session.get(f"{self.base_url}/auth/login").text
            soup = load_html(res)
            token = soup.select_one("input[name='_token']")["value"]
            captcha_url = soup.select_one(".img-captcha")["src"]

            print("Submitting captcha to 2captcha")
            res = self.session.post(
                url="https://2captcha.com/in.php",
                data={
                    "key": twocaptcha_api_key,
                    "json": "1",
                },
                files={
                    "file": ("captcha.jpg", self.session.get(captcha_url).content, "image/jpeg"),
                },
                headers={
                    "User-Agent": "pptu/0.1.0",  # TODO: Get version dynamically
                },
            ).json()
            if res["status"] != 1:
                eprint(f"2Captcha API error: [cyan]{res['request']}[/].")
                return False
            req_id = res["request"]

            print("Waiting for solution.", end="", flush=True)
            while True:
                time.sleep(5)
                res = self.session.get(
                    url="https://2captcha.com/res.php",
                    params={
                        "key": twocaptcha_api_key,
                        "action": "get",
                        "id": req_id,
                        "json": "1",
                    },
                ).json()
                if res["request"] == "CAPCHA_NOT_READY":
                    print(".", end="", flush=True)
                elif res["status"] != 1:
                    eprint(f"2Captcha API error: [cyan]{res['request']}[/].")
                    return False
                else:
                    captcha_answer = res["request"]
                    print(" Received")
                    break

            while True:
                r = self.session.post(
                    url=f"{self.base_url}/auth/login",
                    data={
                        "_token": token,
                        "email_username": username,
                        "password": password,
                        "captcha": captcha_answer,
                    },
                )
                res = r.text

                if "/captcha" in r.url or "Verification failed. You might be a robot!" in res:
                    self.session.post(
                        url="https://2captcha.com/res.php",
                        params={
                            "key": twocaptcha_api_key,
                            "action": "reportbad",
                            "id": req_id,
                        },
                    )

                    if attempt > 5:
                        eprint("Captcha answer rejected too many times, giving up.")
                        return False

                    wprint("Captcha answer rejected, retrying.")
                    attempt += 1
                    continue

                self.session.post(
                    url="https://2captcha.com/res.php",
                    params={
                        "key": twocaptcha_api_key,
                        "action": "reportgood",
                        "id": req_id,
                    },
                )
                done = True
                break

        for cookie in self.session.cookies:
            self.cookie_jar.set_cookie(cookie)
        self.cookies_path.parent.mkdir(parents=True, exist_ok=True)
        self.cookie_jar.save(ignore_discard=True)

        if "/auth/twofa" in r.url:
            print("2FA detected")

            soup = load_html(res)

            r = self.session.post(
                url=r.url,
                data={
                    "_token": soup.select_one("input[name='_token']")["value"],
                    "twofa_code": TOTP(totp_secret).now() if totp_secret else Prompt.ask("Enter 2FA code"),
                },
            )
            if "/auth/twofa" in r.url:
                eprint("TOTP code rejected.")
                print(r.text)
                return False

        if r.url != self.base_url:
            eprint("Login failed - Unknown error.")
            print(r.url)
            return False

        return True

    @property
    def passkey(self):
        res = self.session.get(f"{self.base_url}/account").text
        soup = load_html(res)
        return soup.select_one(".current_pid").text

    def prepare(self, path, mediainfo, snapshots, *, auto):
        if re.search(r"\.S\d+(E\d+)+\.", str(path)):
            print("Detected episode")
            collection = "episode"
        elif re.search(r"\.S\d+\.", str(path)):
            print("Detected season")
            collection = "season"
        elif re.search(r"\.S\d+-S?\d+\.", str(path)):
            collection = "series"
        else:
            collection = "movie"

        if (m := re.search(r"(.+?)\.S\d+(?:E\d+|\.)", path.name)) or (m := re.search(r"(.+?\.\d{4})\.", path.name)):
            title = m.group(1).replace(".", " ")
            print(f"Detected title: [bold cyan]{title}[/]")
        else:
            eprint("Unable to extract title from filename.")
            return False

        season = None
        if collection != "movie":
            if m := re.search(r"\.S(\d+)[E.]", path.name):
                season = int(m.group(1))
            else:
                eprint("Unable to extract season from filename.")
                return False

        episode = None
        if m := re.search(r"\.S\d+E(\d+)\.", path.name):
            episode = int(m.group(1))

        r = self.session.get(self.base_url)
        res = r.text
        soup = load_html(res)
        token = soup.select_one('meta[name="_token"]')["content"]

        year = None
        if m := re.search(r" (\d{4})$", title):
            title = title.replace(m.group(0), "")
            year = int(m.group(1))

        res = self.session.get(
            url=f"{self.base_url}/ajax/movies/{'1' if collection == 'movie' else '2'}",
            params={
                "term": title,
            },
            headers={
                "x-requested-with": "XMLHttpRequest",
            },
            timeout=60,
        ).json()
        print(res, highlight=True)
        r.raise_for_status()
        res = next(x for x in res["data"] if x.get("release_year") == year or not year)
        movie_id = res["id"]
        print(f"Found title: [bold cyan]{res['title']}[/] ([bold green]{res['release_year']}[/])")
        data = {
            "_token": token,
            "type_id": 1 if collection == "movie" else 2,
            "movie_id": movie_id,
            "media_info": mediainfo,
        }
        print(data)

        if not auto and not Confirm.ask("\nContinue with upload?"):
            return False

        torrent_path = self.dirs.user_cache_path / f"{path.name}_files" / f"{path.name}[{self.abbrev}].torrent"
        url = f"{self.base_url}/upload/{'movie' if collection == 'movie' else 'tv'}"
        r = self.session.post(
            url=url,
            data=data,
            files={
                "torrent_file": (torrent_path.name, torrent_path.open("rb"), "application/x-bittorrent"),
            },
            headers={
                "Referer": url,
            },
            timeout=60,
        )
        self.upload_url = r.url
        res = r.text
        soup = load_html(res)

        images = []
        snapshots = snapshots[: len(snapshots) - len(snapshots) % 3]
        for img in snapshots:
            res = self.session.post(
                url=f"{self.base_url}/ajax/image/upload",
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
            ).json()
            print(res, highlight=True)
            r.raise_for_status()
            images.append(res["imageId"])

        if errors := soup.select(".form-error"):
            for error in errors:
                eprint(f"[cyan]{escape(error.text)}[cyan]")
            return False

        self.data = {
            "_token": token,
            "info_hash": soup.select_one('input[name="info_hash"]')["value"],
            "torrent_id": "",
            "type_id": 1 if collection == "movie" else 2,
            "task_id": self.upload_url.split("/")[-1],
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

        return True

    def upload(self, path, mediainfo, snapshots, *, auto):
        print(self.data, highlight=True)

        if not auto and not Confirm.ask("Upload torrent?"):
            return False

        r = self.session.post(url=self.upload_url, data=self.data, timeout=60)
        res = r.text
        soup = load_html(res)
        r.raise_for_status()
        torrent_url = soup.select_one('a[href*="/download/"]')["href"]
        self.session.get(torrent_url, timeout=60)

        return True
