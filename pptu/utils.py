import argparse
import re

import toml
from requests.utils import CaseInsensitiveDict
from rich import print

from pptu.constants import PROG_NAME, PROG_VERSION


class Config:
    def __init__(self, file):
        self._config = CaseInsensitiveDict(toml.load(file))

    def get(self, tracker, key, default=None):
        value = None
        if tracker != "default":
            value = self._config.get(tracker.name, {}).get(key) or self._config.get(tracker.abbrev, {}).get(key)

        return value or self._config.get("default", {}).get(key) or default


class RParse(argparse.ArgumentParser):
    def _print_message(self, message, file=None):
        if message:
            if message.startswith("usage"):
                message = f"[bold cyan]{PROG_NAME}[/bold cyan] {PROG_VERSION}\n\n{message}"
                message = re.sub(r"(-[a-z]+\s*|\[)([A-Z]+)(?=]|,|\s\s|\s\.)", r"\1[bold color(231)]\2[/]", message)
                message = re.sub(r"((-|--)[a-z]+)", r"[{}]\1[/{}]".format("green", "green"), message)
                message = message.replace("usage", "[yellow]USAGE[/yellow]")
                message = message.replace("positional arguments", "[yellow]POSITIONAL ARGUMENTS[/yellow]")
                message = message.replace("options", "[yellow]FLAGS[/yellow]", 1)
                message = message.replace(" file ", "[bold magenta] file [/bold magenta]", 2)
                message = message.replace(self.prog, f"[bold cyan]{self.prog}[/bold cyan]")
            message = f"[not bold white]{message.strip()}[/not bold white]"
            print(message)


class CustomHelpFormatter(argparse.RawTextHelpFormatter):
    def _format_action_invocation(self, action):
        if not action.option_strings or action.nargs == 0:
            return super()._format_action_invocation(action)
        default = self._get_default_metavar_for_optional(action)
        args_string = self._format_args(action, default)
        return ", ".join(action.option_strings) + " " + args_string
