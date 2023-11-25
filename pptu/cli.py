#!/usr/bin/env python3

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


def main() -> None:
    parser = RParse(prog=PROG_NAME)
    parser.add_argument("path",
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
    parser.add_argument("-c", "--confirm",
                        action="store_true",
                        help="ask for confirmation before uploading")
    parser.add_argument("-a", "--auto",
                        action="store_true",
                        help="never prompt for user input")
    parser.add_argument("-ds", "--disable-snapshots",
                        action="store_true",
                        help="disable creating snapshots to description")
    parser.add_argument("-s", "--skip-upload",
                        action="store_true",
                        help="skip upload")
    parser.add_argument("-n", "--note",
                        help="note to add to upload")
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
        for tracker_cls in all_trackers:
            supported_trackers.add_row(tracker_cls.name, tracker_cls.abbrev)
        console = Console()
        console.print(supported_trackers)
        sys.exit(0)

    if not args.trackers:
        parser.error("the following arguments are required: -t/--trackers")
    if not args.path:
        parser.error("the following arguments are required: path")

    trackers = list()
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

        if not tracker.login(auto=args.auto):
            eprint(f"Failed to log in to tracker [cyan]{tracker.name}[/].")
            continue
        for cookie in tracker.session.cookies:
            tracker.cookie_jar.set_cookie(cookie)
        tracker.cookies_path.parent.mkdir(parents=True, exist_ok=True)
        # prevent corrupted cookies file
        try:
            tracker.cookies_path.unlink(missing_ok=True)
        except PermissionError:
            pass
        tracker.cookie_jar.save(ignore_discard=True)

    jobs = list()

    fast_upload = (
        args.fast_upload or (config.get("default", "fast_upload", False) and args.fast_upload is not False)
    )

    for path in args.path:
        if not path.exists():
            eprint(f"File [cyan]{path.name!r}[/] does not exist.")
            continue

        cache_dir = PlatformDirs(appname="pptu", appauthor=False).user_cache_path / f"{path.name}_files"
        cache_dir.mkdir(parents=True, exist_ok=True)

        for tracker in trackers:
            pptu = PPTU(path, tracker, note=args.note, auto=args.auto, snapshots=not args.disable_snapshots)

            print(f"\n[bold green]Creating torrent file for tracker ({tracker.abbrev})[/]")
            pptu.create_torrent()

            if tracker.mediainfo:
                print(f"\n[bold green]Generating MediaInfo ({tracker.abbrev})[/]")
                if not (mediainfo := pptu.get_mediainfo()):
                    eprint("Failed to generate MediaInfo")
                    continue
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
                if args.confirm and pptu.tracker.data:
                    print(pptu.tracker.data, highlight=True)
                if args.skip_upload or (args.confirm and not Confirm.ask("Upload torrent?")):
                    print("Skipping upload")
                    continue
                pptu.upload(mediainfo, snapshots)

    if fast_upload:
        for pptu, mediainfo, snapshots in jobs:
            print(f"\n[bold green]Uploading ({pptu.tracker.abbrev})[/]")
            if args.confirm and pptu.tracker.data:
                print(pptu.tracker.data, highlight=True)
            if args.skip_upload or (args.confirm and not Confirm.ask("Upload torrent?")):
                print("Skipping upload")
                continue
            pptu.upload(mediainfo, snapshots)
            print()


if __name__ == "__main__":
    main()
