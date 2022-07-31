import re
from pathlib import Path

from bs4 import BeautifulSoup
from imdb import Cinemagoer
from rich import print

from pymkt.uploaders import Uploader

ia = Cinemagoer()


class PTPUploader(Uploader):
    def __init__(self):
        super().__init__("PTP")

    def upload(self, path, mediainfo, snapshots, thumbnails, *, auto):
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
        res = self.session.get(
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
            res = self.session.get(
                url="https://passthepopcorn.me/upload.php",
                params={
                    "groupid": groupid,
                },
            ).text
            soup = BeautifulSoup(res, "lxml-html")

            data = {
                "AntiCsrfToken": soup.select_one("[name='AntiCsrfToken']")["value"],
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

            self.session.post(
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
