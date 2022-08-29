import importlib.resources
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import oxipng
from platformdirs import PlatformDirs
from pymediainfo import MediaInfo
from rich.progress import track
from wand.image import Image

from .utils import Config, eprint


class PPTU:
    def __init__(self, file, tracker, *, auto=False):
        self.file = file
        self.tracker = tracker
        self.auto = auto

        dirs = PlatformDirs(appname="pptu", appauthor=False)
        self.cache_dir = dirs.user_cache_path / f"{file.name}_files"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.config = Config(dirs.user_config_path / "config.toml")

        self.num_snapshots = max(
            self.config.get(tracker, "snapshot_columns", 2) * self.config.get(tracker, "snapshot_rows", 2),
            tracker.min_snapshots,
        )

    def create_torrent(self):
        passkey = self.config.get(self.tracker, "passkey") or self.tracker.passkey
        if not passkey and "{passkey}" in self.tracker.announce_url:
            eprint(f"Passkey not found for tracker [cyan]{self.tracker.name}[cyan].")
            return False

        subprocess.run([
            "torrenttools",
            "edit",
            "--no-created-by",
            "--no-creation-date",
            "-a", self.tracker.announce_url.format(passkey=passkey),
            "-s", self.tracker.source,
            "-p", "on",
            "-o", self.cache_dir / f"{self.file.name}[{self.tracker.abbrev}].torrent",
            self.cache_dir / f"{self.file.name}.torrent",
        ], check=True)

        return True

    def get_mediainfo(self):
        mediainfo_path = self.cache_dir / "mediainfo.txt"
        if self.tracker.all_files and self.file.is_dir():
            mediainfo_path = self.cache_dir / "mediainfo_alt.txt"

        if mediainfo_path.exists():
            mediainfo = mediainfo_path.read_text()
        else:
            if self.file.is_file() or self.tracker.all_files:
                f = self.file
            else:
                f = list(sorted([*self.file.glob("*.mkv"), *self.file.glob("*.mp4")]))[0]

            p = subprocess.run(
                ["mediainfo", f], cwd=self.file.parent, check=True, capture_output=True, encoding="utf-8"
            )
            mediainfo = p.stdout
            mediainfo_path.write_text(mediainfo)

        mediainfo = [x.strip() for x in re.split(r"\n\n(?=General)", mediainfo)]
        if not self.tracker.all_files:
            mediainfo = mediainfo[0]
        return mediainfo

    def generate_snapshots(self, step):
        num_snapshots = self.num_snapshots

        if self.file.is_dir() or self.tracker.all_files:
            # TODO: Handle case when number of files < num_snapshots
            files = list(sorted([*self.file.glob("*.mkv"), *self.file.glob("*.mp4")]))
        elif self.file.is_file():
            files = [self.file] * num_snapshots

        if self.tracker.all_files:
            num_snapshots = len(files)

        snapshots = []

        print()
        for i in track(
            range(num_snapshots), description=f"[bold green]\\[{step}] Generating snapshots ({self.tracker.abbrev})[/]"
        ):
            mediainfo_obj = MediaInfo.parse(files[i])
            duration = float(mediainfo_obj.video_tracks[0].duration) / 1000
            interval = duration / (num_snapshots + 1)

            snap = self.cache_dir / "{num:02}{alt}.png".format(num=i + 1, alt="_alt" if self.tracker.all_files else "")
            if not snap.exists():
                subprocess.run([
                    "ffmpeg",
                    "-y",
                    "-v", "error",
                    "-ss", str(interval * (i + 1) if len(set(files)) == 1 else duration / 2),
                    "-i", files[i],
                    "-vf", "scale='max(sar,1)*iw':'max(1/sar,1)*ih'",
                    "-frames:v", "1",
                    snap,
                ], check=True)
                with Image(filename=snap) as img:
                    img.depth = 8
                    img.save(filename=snap)
                oxipng.optimize(snap)
            snapshots.append(snap)

        return snapshots

    def upload(self, mediainfo, snapshots):
        if not self.tracker.upload(self.file, mediainfo, snapshots, auto=self.auto):
            eprint(f"Upload to [cyan]{self.tracker.name}[/cyan] failed.")
            return

        torrent_path = self.cache_dir / f"{self.file.name}[{self.tracker.abbrev}].torrent"
        if watch_dir := self.config.get(self.tracker, "watch_dir"):
            watch_dir = Path(watch_dir).expanduser()
            subprocess.run(
                [
                    sys.executable,
                    importlib.resources.path("pyrosimple.scripts", "chtor.py"),
                    "-H", self.file,
                    torrent_path,
                ],
                env={**os.environ, "PYRO_RTORRENT_RC": os.devnull},
                check=True,
            )
            shutil.copyfile(torrent_path, watch_dir / torrent_path.name)
