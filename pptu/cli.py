#!/usr/bin/env python3

from copy import copy
from pathlib import Path

import requests
from platformdirs import PlatformDirs
from requests.adapters import HTTPAdapter, Retry
from rich import print

from . import uploaders
from .constants import PROG_NAME, PROG_VERSION
from .pptu import PPTU
from .uploaders import Uploader
from .utils import RParse, eprint


dirs = PlatformDirs(appname="pptu", appauthor=False)


def main():
    parser = RParse(prog=PROG_NAME)
    parser.add_argument("file",
                        type=Path,
                        nargs="+",
                        help="files/directories to create torrents for")
    parser.add_argument("-v", "--version",
                        action="version",
                        version=f"[bold cyan]{PROG_NAME}[/bold cyan] [not bold white]{PROG_VERSION}[/not bold white]",
                        help="show version and exit")
    parser.add_argument("-t", "--trackers",
                        metavar="ABBREV",
                        type=lambda x: x.split(","),
                        required=True,
                        help="tracker(s) to upload torrents to (required)")
    parser.add_argument("-a", "--auto",
                        action="store_true",
                        help="upload without confirmation")
    args = parser.parse_args()

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

    trackers = []

    print("[bold green]\\[1/6] Logging in to trackers[/bold green]")
    for i, tracker_name in enumerate(copy(args.trackers)):
        try:
            tracker = next(
                x for x in vars(uploaders).values()
                if isinstance(x, type) and x != Uploader and issubclass(x, Uploader)
                and (x.name.casefold() == tracker_name.casefold() or x.abbrev.casefold() == tracker_name.casefold())
            )()
        except StopIteration:
            eprint(f"Tracker [cyan]{tracker_name}[/cyan] not found.")
            continue
        trackers.append(tracker)

        print(f"[bold cyan]\\[{i + 1}/{len(trackers)}] Logging in to {tracker.abbrev}")

        if not tracker.login():
            eprint(f"Failed to log in to tracker [cyan]{tracker.name}[/cyan].")
            continue
        for cookie in tracker.session.cookies:
            tracker.cookie_jar.set_cookie(cookie)
        tracker.cookies_path.parent.mkdir(parents=True, exist_ok=True)
        tracker.cookie_jar.save(ignore_discard=True)

    for i, file in enumerate(args.file):
        if not file.exists():
            eprint(f"File [cyan]{file.name!r}[/cyan] does not exist.")
            continue

        for tracker in trackers:
            pptu = PPTU(file, tracker, auto=args.auto)

            print("\n[bold green]\\[2/6] Creating torrent files[/bold green]")
            pptu.create_torrent()

            print("\n[bold green]\\[3/6] Generating MediaInfo[/bold green]")
            mediainfo = pptu.get_mediainfo()
            print("Done!")

            # [4/6] Generating snapshots
            snapshots = pptu.generate_snapshots()

            print("\n[bold green]\\[5/6] Generating thumbnails[/bold green]")
            thumbnails = pptu.generate_thumbnails(snapshots)
            print("Done!")

            print("\n[bold green]\\[6/6] Uploading[/bold green]")
            pptu.upload(mediainfo, snapshots, thumbnails)

            print()


if __name__ == "__main__":
    main()
