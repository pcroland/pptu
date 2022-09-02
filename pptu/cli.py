#!/usr/bin/env python3

import subprocess
import sys
import time
from pathlib import Path

from platformdirs import PlatformDirs
from rich.console import Console
from rich.prompt import Confirm
from rich.table import Table

from . import uploaders
from .constants import PROG_NAME, PROG_VERSION
from .pptu import PPTU
from .uploaders import Uploader
from .utils import Config, RParse, eprint, print, wprint


dirs = PlatformDirs(appname="pptu", appauthor=False)


def main():
    parser = RParse(prog=PROG_NAME)
    parser.add_argument("file",
                        type=Path,
                        nargs="*",
                        help="files/directories to create torrents for")
    parser.add_argument("-v", "--version",
                        action="version",
                        version=f"[bold cyan]{PROG_NAME}[/] [not bold white]{PROG_VERSION}[/]",
                        help="show version and exit")
    parser.add_argument("-t", "--trackers",
                        metavar="ABBREV",
                        type=lambda x: x.split(","),
                        help="tracker(s) to upload torrents to (required)")
    parser.add_argument("-f", "--fast-upload",
                        action="store_true",
                        default=None,
                        help="only upload when every step is done for every input")
    parser.add_argument("-nf", "--no-fast-upload",
                        dest="fast_upload",
                        action="store_false",
                        default=None,
                        help="disable fast upload even if enabled in config")
    parser.add_argument("-a", "--auto",
                        action="store_true",
                        help="upload without confirmation")
    parser.add_argument("-s", "--skip-upload",
                        action="store_true",
                        help="skip upload")
    parser.add_argument("-lt", "--list-trackers",
                        action="store_true",
                        help="list supported trackers")
    if len(sys.argv) == 1:
        parser.print_help(sys.stderr)
        if getattr(sys, "frozen", False):
            wprint("\nPlease use PPTU from the command line if you double-clicked the standalone build.")
            time.sleep(10)
        sys.exit(1)
    args = parser.parse_args()

    config = Config(dirs.user_config_path / "config.toml")

    all_trackers = [
        x for x in vars(uploaders).values()
        if isinstance(x, type) and x != Uploader and issubclass(x, Uploader)
    ]

    if args.list_trackers:
        supported_trackers = Table(title="Supported trackers", title_style="not italic bold magenta")
        supported_trackers.add_column("Site", style="cyan")
        supported_trackers.add_column("Abbreviation", style="bold green")
        for tracker in all_trackers:
            supported_trackers.add_row(tracker.name, tracker.abbrev)
        console = Console()
        console.print(supported_trackers)
        sys.exit(0)

    if not args.trackers:
        parser.error("the following arguments are required: -t/--trackers")
    if not args.file:
        parser.error("the following arguments are required: file")

    trackers = []
    for tracker_name in args.trackers:
        try:
            tracker = next(
                x for x in all_trackers
                if (x.name.casefold() == tracker_name.casefold() or x.abbrev.casefold() == tracker_name.casefold())
            )()
        except StopIteration:
            eprint(f"Tracker [cyan]{tracker_name}[/] not found.")
            continue
        trackers.append(tracker)

    print("[bold green]Logging in to trackers[/]")
    for tracker in trackers:
        print(f"[bold cyan]Logging in to {tracker.abbrev}[/]")

        if not tracker.login():
            eprint(f"Failed to log in to tracker [cyan]{tracker.name}[/].")
            continue
        for cookie in tracker.session.cookies:
            tracker.cookie_jar.set_cookie(cookie)
        tracker.cookies_path.parent.mkdir(parents=True, exist_ok=True)
        tracker.cookie_jar.save(ignore_discard=True)

    jobs = []

    for file in args.file:
        if not file.exists():
            eprint(f"File [cyan]{file.name!r}[/] does not exist.")
            continue

        cache_dir = PlatformDirs(appname="pptu", appauthor=False).user_cache_path / f"{file.name}_files"
        cache_dir.mkdir(parents=True, exist_ok=True)

        print("\n[bold green]Creating initial torrent file[/]")
        base_torrent_path = cache_dir / f"{file.name}.torrent"
        if not base_torrent_path.exists():
            subprocess.run([
                "torrenttools",
                "create",
                "--no-created-by",
                "--no-creation-date",
                "--no-cross-seed",
                "--exclude", r".*\.(ffindex|jpg|nfo|png|srt|torrent|txt)$",
                "-o", base_torrent_path,
                file,
            ], check=True)
        if not base_torrent_path.exists():
            sys.exit(1)

        fast_upload = (
            args.fast_upload or (config.get("default", "fast_upload", False) and args.fast_upload is not False)
        )

        for tracker in trackers:
            pptu = PPTU(file, tracker, auto=args.auto)

            print(f"[bold green]Creating torrent file for tracker ({tracker.abbrev})[/]")
            pptu.create_torrent()

            print(f"\n[bold green]Generating MediaInfo ({tracker.abbrev})[/]")
            mediainfo = pptu.get_mediainfo()
            print("Done!")

            # Generating snapshots
            snapshots = pptu.generate_snapshots()

            print(f"\n[bold green]Preparing upload ({tracker.abbrev})[/]")
            if not pptu.prepare(mediainfo, snapshots):
                continue

            if fast_upload:
                jobs.append((pptu, mediainfo, snapshots))
            else:
                print(f"\n[bold green]Uploading ({tracker.abbrev})[/]")
                if not args.auto and pptu.data:
                    print(pptu.data)
                if args.skip_upload or (not args.auto and not Confirm.ask("Upload torrent?")):
                    print("Skipping upload")
                    continue
                pptu.upload(mediainfo, snapshots)
            print()

    if fast_upload:
        for pptu, mediainfo, snapshots in jobs:
            print(f"\n[bold green]Uploading ({pptu.tracker.abbrev})[/]")
            if args.skip_upload or (not args.auto and not Confirm.ask("Upload torrent?")):
                print("Skipping upload")
                continue
            pptu.upload(mediainfo, snapshots)
            print()


if __name__ == "__main__":
    main()
