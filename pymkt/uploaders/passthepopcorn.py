import re

from bs4 import BeautifulSoup
from imdb import Cinemagoer
from pymediainfo import MediaInfo
from rich import print

from pymkt.uploaders import Uploader

ia = Cinemagoer()


class PassThePopcornUploader(Uploader):
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

        print(f"IMDb: [cyan][bold]{title}[/bold] [not bold]({year})[/not bold][/cyan]")

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
        groupid = res[0].get("groupid")

        torrent_path = self.dirs.user_cache_path / f"{path}_files" / f"{path.name}[PTP].torrent"

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

        data = {
            "AntiCsrfToken": soup.select_one("[name='AntiCsrfToken']")["value"],
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

        self.session.post(
            url="https://passthepopcorn.me/upload.php",
            params={
                "groupid": groupid,
            },
            data=data,
            files={
                "file": (torrent_path.name, torrent_path.open("rb"), "application/x-bittorrent"),
            },
        )
