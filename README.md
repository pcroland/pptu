# pymkt

Python torrent creator and auto-uploader

## Requirements
* Python 3.8+
* Python package dependencies (`poetry install` or `pip install .`)
* torrenttools (for creating torrents)
* MediaInfo CLI (for generating tech info)
* FFmpeg (for generating snapshots)

## Supported trackers
Name           | Abbreviation | Server upload allowed
-------------- | ------------ | -------------------------------------------------------------------
AvistaZ        | `AvZ`        | :white_check_mark: Yes, if added as seedbox in profile
BroadcasTheNet | `BTN`        | :warning: Dedicated servers only, requires staff approval
CinemaZ        | `CZ`         | :white_check_mark: Yes, if added as seedbox in profile
HDBits         | `HDB`        | :white_check_mark: Yes, if IP whitelisted in profile or 2FA enabled
PassThePopcorn | `PTP`        | :warning: Dedicated servers only, requires staff approval
PrivateHD      | `PHD`        | :white_check_mark: Yes, if added as seedbox in profile

## Usage
Copy `config.example.toml` to `~/.config/pymkt/config.toml` and edit it as appropriate.
In the global section you can specify a proxy and/or a watch directory. These can be overridden per tracker if needed.
Make sure to set a passkey for each tracker, and you can optionally specify a proxy as well.

Place cookies in `~/.local/share/pymkt/cookies/TRACKER.txt` where `TRACKER` is the name or the abbreviation of the
tracker above (all lowercase).

Install dependencies and the script with `./install.sh`. You can re-run the script to update after a git pull.

```
$ mkt -t tracker1,tracker2,tracker3 FILE_OR_FOLDER
```
Options:
* `--auto`: Skip prompts to confirm autofilled data is correct and upload fully automatically
  (unless we're unable to infer some info without user input)
* `--snapshots`: Override number of snapshots to take (default: 4).

## Notes
Movie support for BTN and miniseries support for PTP is not yet implemented.
