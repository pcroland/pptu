import argparse
import re
import sys

import oxipng
import toml
from bs4 import BeautifulSoup
from requests.utils import CaseInsensitiveDict
from rich import print
from wand.image import Image

from .constants import PROG_NAME, PROG_VERSION


class Config:
    def __init__(self, file):
        self._config = CaseInsensitiveDict(toml.load(file))

    def get(self, tracker, key, default=None):
        value = None
        if tracker != "default":
            value = self._config.get(tracker.name, {}).get(key) or self._config.get(tracker.abbrev, {}).get(key)

        return value or self._config.get("default", {}).get(key) or default


class RParse(argparse.ArgumentParser):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("formatter_class", lambda prog: CustomHelpFormatter(prog))
        super().__init__(*args, **kwargs)

    def _print_message(self, message, file=None):
        if message:
            if message.startswith("usage"):
                message = f"[bold cyan]{PROG_NAME}[/] {PROG_VERSION}\n\n{message}"
                message = re.sub(r"(-[a-z]+\s*|\[)([A-Z]+)(?=]|,|\s\s|\s\.)", r"\1[bold color(231)]\2[/]", message)
                message = re.sub(r"((-|--)[a-z]+)", r"[green]\1[/]", message)
                message = message.replace("usage", "[yellow]USAGE[/]")
                message = message.replace("positional arguments", "[yellow]POSITIONAL ARGUMENTS[/]")
                message = message.replace("options", "[yellow]FLAGS[/]", 1)
                message = message.replace(" file ", "[bold magenta] file [/]", 2)
                message = message.replace(self.prog, f"[bold cyan]{self.prog}[/]")
            message = f"[not bold default]{message.strip()}[/]"
            print(message)


class CustomHelpFormatter(argparse.RawTextHelpFormatter):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("max_help_position", 80)
        super().__init__(*args, **kwargs)

    def _format_action_invocation(self, action):
        if not action.option_strings or action.nargs == 0:
            return super()._format_action_invocation(action)
        default = self._get_default_metavar_for_optional(action)
        args_string = self._format_args(action, default)
        return ", ".join(action.option_strings) + " " + args_string


def wprint(inp, newline_before=False):
    if newline_before: print()
    print(f"[bold color(231) on yellow]WARNING:[/] [yellow]{inp}[/]")


def eprint(inp, newline_before=False, fatal=False, exit_code=1):
    if newline_before: print()
    print(f"[bold color(231) on red]ERROR:[/] [red]{inp}[/]")
    if fatal:
        sys.exit(exit_code)


def load_html(text):
    return BeautifulSoup(text, "lxml-html")


def generate_thumbnails(snapshots, width=300):
    width = int(width)
    for snap in snapshots:
        thumb = snap.with_stem(f"{snap.stem}_thumb_{width}")
        if not thumb.exists():
            with Image(filename=snap) as img:
                img.resize(width, round(img.height / (img.width / width)))
                img.depth = 8
                img.save(filename=thumb)
            oxipng.optimize(thumb)
        yield thumb


__all__ = ["Config", "RParse"]
