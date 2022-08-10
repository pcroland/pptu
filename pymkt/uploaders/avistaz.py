import re
import sys
import uuid

from bs4 import BeautifulSoup
from rich import print

from pymkt.uploaders import Uploader


class AvistaZUploader(Uploader):
    COLLECTION_MAP = {
        "movie": None,
        "episode": 1,
        "season": 2,
        "series": 3,
    }

    def upload(self, path, mediainfo, snapshots, thumbnails, *, auto):
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
            print(f"Detected title: [bold][cyan]{title}[/cyan][/bold]")
        else:
            print("[red][bold]ERROR[/bold]: Unable to extract title from filename[/red]")
            sys.exit(1)

        season = None
        if collection != "movie":
            if m := re.search(r"\.S(\d+)[E.]", path.name):
                season = int(m.group(1))
            else:
                print("[red][bold]ERROR[/bold]: Unable to extract season from filename[/red]")

        episode = None
        if m := re.search(r"\.S\d+E(\d+)\.", path.name):
            episode = int(m.group(1))

        r = self.session.get(url="https://avistaz.to/", timeout=60)
        self.session.cookies.save(ignore_expires=True, ignore_discard=True)
        print(r, r.url)
        res = r.text
        soup = BeautifulSoup(res, "lxml-html")
        token = soup.select_one('meta[name="_token"]')["content"]

        year = None
        if m := re.search(r" (\d{4})$", title):
            title = title.replace(m.group(0), "")
            year = int(m.group(1))

        r = self.session.get(
            url=f"https://avistaz.to/ajax/movies/{'1' if collection == 'movie' else '2'}",
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
        res = next(x for x in res["data"] if x.get("release_year") == year or not year)
        movie_id = res["id"]
        print(
            f'Found title: [bold][cyan]{res["title"]}[/cyan][/bold] ([bold][green]{res["release_year"]}[/green][/bold])'
        )
        data = {
            "_token": token,
            "type_id": 1 if collection == "movie" else 2,
            "movie_id": movie_id,
            "media_info": mediainfo,
        }
        print({**data, "_token": "[hidden]", "media_info": "[hidden]"})

        if not auto:
            print("Press Enter to continue")
            input()

        torrent_path = self.dirs.user_cache_path / f"{path}_files" / f"{path.name}[AvZ].torrent"
        r = self.session.post(
            url=f"https://avistaz.to/upload/{'movie' if collection == 'movie' else 'tv'}",
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
            img = torrent_path.parent / f"{i}.png"
            r = self.session.post(
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
            "type_id": 1 if collection == "movie" else 2,
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

        r = self.session.post(url=upload_url, data=data, timeout=60)
        print(r)
        res = r.text
        soup = BeautifulSoup(res, "lxml-html")
        print(soup.prettify())
        r.raise_for_status()
        torrent_url = soup.select_one('a[href*="/download/"]')["href"]
        self.session.get(torrent_url, timeout=60)

        return True
