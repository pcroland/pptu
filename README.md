# pymkt

Python torrent creator and auto-uploader

## Requirements
* Python 3.8+
* Python package dependencies (`poetry install` or `pip install .`)
* torrenttools (for creating torrents)
* MediaInfo CLI (for generating tech info)
* FFmpeg (for generating snapshots)
* ImageMagick + oxipng (for optimizing snapshots) [optional but recommended]
* `PTPIMG_API_KEY` environment variable (for uploading snapshots)

## Supported trackers
Name           | Abbreviation | Server upload allowed
-------------- | ------------ | -------------------------------------------------------------------
AvistaZ        | `avz`        | :white_check_mark: Yes, if added as seedbox in profile
BroadcasTheNet | `btn`        | :warning: Dedicated servers only, requires staff approval
HDBits         | `hdb`        | :white_check_mark: Yes, if IP whitelisted in profile or 2FA enabled
PassThePopcorn | `ptp`        | :warning: Dedicated servers only, requires staff approval

## Usage
Copy `config.example.toml` to `~/.config/pymkt/config.toml` and edit it as appropriate.
In the global section you can specify a proxy and/or a watch directory. These can be overridden per tracker if needed.
Make sure to set a passkey for each tracker, and you can optionally specify a proxy as well.

Place cookies in `~/.local/share/pymkt/cookies/TRACKER.txt` where `TRACKER` is the name or the abbreviation of the
tracker above (all lowercase).

Install dependencies and the script with `poetry install`.

```
$ mkt -t tracker1,tracker2,tracker3 FILE_OR_FOLDER
```
Options:
* `--auto`: Skip prompts to confirm autofilled data is correct and upload fully automatically
  (unless we're unable to infer some info without user input)
* `--short`: Temporary hack for files shorter than 20 minutes (5 minutes for full seasons),
  takes screenshots at 1/2/3/4 minutes rather than 5/10/15/20. Eventually duration will be
  auto-detected.
* `--snapshots`: Override number of snapshots to take (default: 4).

## Notes
Movie support for BTN and miniseries support for PTP is not yet implemented.
