#!/usr/bin/env python3

import argparse
import importlib.resources
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from copy import copy
from pathlib import Path

import oxipng
import requests
from platformdirs import PlatformDirs
from pymediainfo import MediaInfo
from requests.adapters import HTTPAdapter, Retry
from rich import print
from rich.progress import track
from ruamel.yaml import YAML
from wand.image import Image

from pymkt import uploaders
from pymkt.utils import Config

prog_name = 'mkt'
prog_version = '2022.08.28.1'

class RParse(argparse.ArgumentParser):
    def _print_message(self, message, file=None):
        if message:
            if message.startswith('usage'):
                message = f'[bold cyan]{prog_name}[/bold cyan] {prog_version}\n\n{message}'
                message = re.sub(r'(-[a-z]+\s*|\[)([A-Z]+)(?=]|,|\s\s|\s\.)', r'\1[{}]\2[/{}]'.format('bold color(231)', 'bold color(231)'), message)
                message = re.sub(r'((-|--)[a-z]+)', r'[{}]\1[/{}]'.format('green', 'green'), message)
                message = message.replace('usage', '[yellow]USAGE[/yellow]')
                message = message.replace('positional arguments', '[yellow]POSITIONAL ARGUMENTS[/yellow]')
                message = message.replace('options', '[yellow]FLAGS[/yellow]', 1)
                message = message.replace(' file ', '[bold magenta] file [/bold magenta]', 2)
                message = message.replace(self.prog, f'[bold cyan]{self.prog}[/bold cyan]')
            message = f'[not bold white]{message.strip()}[/not bold white]'
            print(message)

class CustomHelpFormatter(argparse.RawTextHelpFormatter):
    def _format_action_invocation(self, action):
        if not action.option_strings or action.nargs == 0:
            return super()._format_action_invocation(action)
        default = self._get_default_metavar_for_optional(action)
        args_string = self._format_args(action, default)
        return ', '.join(action.option_strings) + ' ' + args_string


def main():
    parser = RParse(
        prog=prog_name,
        formatter_class=lambda prog: CustomHelpFormatter(prog, max_help_position=80))
    parser.add_argument("file",
                        type=Path,
                        nargs="+",
                        help="files/directories to create torrents for")
    parser.add_argument("-v", "--version",
                        action='version',
                        version=f'[bold cyan]{prog_name}[/bold cyan] [not bold white]{prog_version}[/not bold white]',
                        help='show version and exit')
    parser.add_argument("-t", "--trackers",
                        metavar='ABBREV',
                        type=lambda x: x.split(","), required=True,
                        help="tracker(s) to upload torrents to (required)")
    parser.add_argument("--auto",
                        action="store_true",
                        help="upload without confirmation")
    args = parser.parse_args()

    dirs = PlatformDirs(appname="pymkt", appauthor=False)

    config = Config(dirs.user_config_path / "config.toml")

    session = requests.Session()
    for scheme in ("http://", "https://"):
        session.mount(
            scheme,
            HTTPAdapter(
                max_retries=Retry(
                    total=5,
                    backoff_factor=1,
                    allowed_methods=["DELETE", "GET", "HEAD", "OPTIONS", "POST", "PUT", "TRACE"],
                    status_forcelist=[429, 500, 502, 503, 504],
                    raise_on_status=False,
                ),
            ),
        )

    trackers = {}

    trackers_json = importlib.resources.path("pymkt", "trackers.json")

    for i, file in enumerate(args.file):
        if not file.exists():
            print(f"[red][bold]ERROR[/bold]: File {file.name!r} does not exist[/red]")
            continue

        d = dirs.user_cache_path / f"{file.name}_files"
        d.mkdir(parents=True, exist_ok=True)

        if i == 0:
            print(r"[bold green]\[1/6] Logging in to trackers[/bold green]")
            for i, tracker_name in enumerate(copy(args.trackers)):
                try:
                    tracker = trackers[tracker_name] = next(
                        x for x in vars(uploaders).values()
                        if isinstance(x, type)
                        and x != uploaders.Uploader
                        and issubclass(x, uploaders.Uploader)
                        and (
                            x.name.casefold() == tracker_name.casefold()
                            or x.abbrev.casefold() == tracker_name.casefold()
                        )
                    )
                except StopIteration:
                    print(f"[red][bold]ERROR[/bold]: Tracker {tracker_name} not found[/red]")
                    args.trackers.remove(tracker_name)
                    continue

                print(f"[bold cyan]\\[{i + 1}/{len(trackers)}] Logging in to {tracker.abbrev}")

                uploader = tracker()

                if not uploader.login():
                    print(f"[red][bold]ERROR[/bold]: Failed to log in to tracker {tracker.name}[/red]")
                    continue
                for cookie in uploader.session.cookies:
                    uploader.cookie_jar.set_cookie(cookie)
                uploader.cookies_path.parent.mkdir(parents=True, exist_ok=True)
                uploader.cookie_jar.save(ignore_discard=True)

                passkey = config.get(tracker, "passkey") or uploader.passkey
                if not passkey and tracker.require_passkey:
                    print(f"[red][bold]ERROR[/bold]: Passkey not defined in config for tracker {tracker.name}[/red]")
                    args.trackers.remove(tracker_name)
                    continue

        print("\n[bold green]\\[2/6] Creating torrent files[/bold green]")
        base_torrent_path = d / f"{file.name}.torrent"
        if not base_torrent_path.exists():
            subprocess.run([
                "torrenttools",
                "create",
                "--no-created-by",
                "--no-creation-date",
                "--no-cross-seed",
                "--exclude", r".*\.(txt|nfo|png|jpg|ffindex|srt|torrent)$",
                "-o",
                base_torrent_path,
                file,
            ], check=True)

        for tracker_name in args.trackers:
            tracker = trackers[tracker_name]

            with tempfile.NamedTemporaryFile(suffix=".yml") as tmp:
                YAML().dump({
                    "tracker-parameters": {
                        tracker.name: {
                            "pid": tracker().passkey,
                        },
                    },
                }, tmp)
                subprocess.run([
                    "torrenttools",
                    "--trackers-config", trackers_json,
                    "--config", tmp.name,
                    "edit",
                    "--no-created-by",
                    "--no-creation-date",
                    "-a", tracker.name,
                    "-s", next(
                        x for x in json.loads(trackers_json.read_text()) if x["name"] == tracker.name
                    )["source"],
                    "-o", d / f"{file.name}[{tracker.abbrev}].torrent",
                    d / f"{file.name}.torrent",
                ], check=True)

        cur_uploaders = []
        for i, tracker_name in enumerate(args.trackers):
            tracker = trackers[tracker_name]
            cur_uploaders.append(tracker)

        print("\n[bold green]\\[3/6] Generating MediaInfo[/bold green]")
        if file.is_file() or any(x.all_files for x in cur_uploaders):
            f = file
        else:
            f = list(sorted([*file.glob("*.mkv"), *file.glob("*.mp4")]))[0]
        p = subprocess.run(["mediainfo", f], cwd=file.parent, check=True, capture_output=True, encoding="utf-8")
        mediainfo = [x.strip() for x in re.split(r"\n\n(?=General)", p.stdout)]

        print("Done!")

        # Generating snapshots
        num_snapshots = max(
            config.get("default", "snapshot_columns") * config.get("default", "snapshot_rows"),
            max(x.min_snapshots for x in cur_uploaders),
        )
        has_all_files = any(x.all_files for x in cur_uploaders)
        if file.is_dir() or has_all_files:
            # TODO: Handle case when number of files < args.snapshots
            files = list(sorted([*file.glob("*.mkv"), *file.glob("*.mp4")]))
        elif file.is_file():
            files = [file] * num_snapshots
        if has_all_files:
            num_snapshots = len(files)
        snapshots = []
        print()
        for i in track(range(num_snapshots), description="[bold green]\\[4/6] Generating snapshots[/bold green]"):
            mediainfo_obj = MediaInfo.parse(files[i])
            duration = float(mediainfo_obj.video_tracks[0].duration) / 1000
            interval = duration / (num_snapshots + 1)

            snap = d / f"{(i + 1):02}.png"
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

        print("\n[bold green]\\[5/6] Generating thumbnails[/bold green]")
        thumbnails = []
        for i in range(num_snapshots):
            thumb = d / f"{(i + 1):02}_thumb.png"
            if not thumb.exists():
                with Image(filename=snapshots[i]) as img:
                    img.resize(300, round(img.height / (img.width / 300)))
                    img.depth = 8
                    img.save(filename=thumb)
                oxipng.optimize(thumb)
            thumbnails.append(thumb)
        print("Done!")

        print("\n[bold green]\\[6/6] Uploading[/bold green]")
        for i, tracker_name in enumerate(args.trackers):
            tracker = trackers[tracker_name]
            print(f"[bold cyan]\\[{i + 1}/{len(args.trackers)}] Uploading to {tracker.abbrev}[/bold cyan]")
            uploader = tracker()
            mediainfo_tmp = mediainfo
            snapshots_tmp = snapshots
            if not tracker.all_files:
                mediainfo_tmp = mediainfo[0]
                snapshots_tmp = snapshots[:args.snapshots]
            if uploader.upload(file, mediainfo_tmp, snapshots_tmp, thumbnails, auto=args.auto):
                torrent_path = d / f"{file.name}[{tracker.abbrev}].torrent"
                if watch_dir := config.get(tracker, "watch_dir"):
                    watch_dir = Path(watch_dir).expanduser()
                    subprocess.run(
                        [
                            sys.executable,
                            importlib.resources.path("pyrosimple.scripts", "chtor.py"),
                            "-H", file,
                            torrent_path,
                        ],
                        env={**os.environ, "PYRO_RTORRENT_RC": os.devnull},
                        check=True,
                    )
                    shutil.copyfile(torrent_path, watch_dir / torrent_path.name)
            else:
                print(f"[red][bold]ERROR[/bold]: Upload to {tracker.name} failed[/red]")
            print()


if __name__ == "__main__":
    main()
