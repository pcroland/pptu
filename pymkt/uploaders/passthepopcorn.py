import os
import re

from bs4 import BeautifulSoup
from imdb import Cinemagoer
from pymediainfo import MediaInfo
from rich import print
from rich.markup import escape

from pymkt.uploaders import Uploader

ia = Cinemagoer()


class PassThePopcornUploader(Uploader):
    name = "PassThePopcorn"
    abbrev = "PTP"
    all_files = True

    def upload(self, path, mediainfo, snapshots, thumbnails, *, auto):
        imdb = None
        if (m := re.search(r"(.+?)\.S\d+(?:E\d+|\.)", path.name)) or (m := re.search(r"(.+?\.\d{4})\.", path.name)):
            title = re.sub(r" (\d{4})$", r" (\1)", m.group(1).replace(".", " "))
            print(f"Detected title: [bold][cyan]{title}[/cyan][/bold]")

            if imdb_results := ia.search_movie(title):
                imdb = f"https://www.imdb.com/title/tt{imdb_results[0].movieID}/"
        else:
            print("[yellow][bold]WARNING[/bold]: Unable to extract title from filename[/yellow]")
        imdb = imdb or input("Enter IMDb URL: ")

        imdb_movie = ia.get_movie(re.search(r"tt(\d+)", imdb).group(1))
        title = imdb_movie.data["original title"]
        year = imdb_movie.data["year"]

        print(f"IMDb: [cyan][bold]{title}[/bold] [not bold]({year})[/not bold][/cyan]")

        groupid = None
        torrent_info = self.session.get(
            url="https://passthepopcorn.me/ajax.php",
            params={
                "action": "torrent_info",
                "imdb": imdb,
                "fast": "1",
            },
        ).json()[0]
        print(torrent_info)
        groupid = torrent_info.get("groupid")

        torrent_path = self.dirs.user_cache_path / f"{path.name}_files" / f"{path.name}[PTP].torrent"

        res = self.session.get(
            url="https://passthepopcorn.me/upload.php",
            params={
                "groupid": groupid,
            },
        ).text
        soup = BeautifulSoup(res, "lxml-html")

        if path.is_dir():
            file = list(sorted([*path.glob("*.mkv"), *path.glob("*.mp4")]))[0]
        else:
            file = path
        mediainfo_obj = MediaInfo.parse(file)
        no_eng_subs = all(not x.language.startswith("en") for x in mediainfo_obj.audio_tracks) and all(
            not x.language.startswith("en") for x in mediainfo_obj.text_tracks
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
            print("Detected series")
            type_ = "Miniseries"
            desc = ""
            for i in range(len(mediainfo)):
                desc += "[mi]\n{mediainfo}\n[/mi]\n{snapshots}\n\n".format(
                    mediainfo=mediainfo[i],
                    snapshots=snapshot_urls[i],
                )
        else:
            # TODO: Detect other types
            print("Detected movie")
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
        print(f"Detected source: [bold cyan]{source}[/bold cyan]")

        data = {
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

        res = self.session.post(
            url="https://passthepopcorn.me/ajax.php",
            params={
                "action": "preview_upload",
            },
            data={
                "ReleaseDescription": data["release_desc"],
                "AntiCsrfToken": data["AntiCsrfToken"],
            },
        ).json()
        data.update(
            {
                "subtitles[]": res["SubtitleIds"],
            }
        )

        print(data)

        if not auto:
            print("Press Enter to upload")
            input()

        res = self.session.post(
            url="https://passthepopcorn.me/upload.php",
            params={
                "groupid": groupid,
            },
            data=data,
            files={
                "file_input": (torrent_path.name, torrent_path.open("rb"), "application/x-bittorrent"),
            },
        ).text
        soup = BeautifulSoup(res, "lxml-html")
        if error := soup.select_one(".alert--error"):
            print(f"[red][bold]ERROR[/bold]: {escape(error.get_text())}[/red]")
            return False

        return True
