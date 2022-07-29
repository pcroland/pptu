# pymkt

Python torrent creator and auto-uploader

## Requirements
* Python 3.8+
* Python package dependencies (`poetry install` or `pip install .`)
* torrenttools (for creating torrents)
* `chtor` from pyrocore (for creating fast resume metadata).
  This dependency will probably be eliminated eventually.
* MediaInfo CLI (for generating tech info)
* FFmpeg (for creating snapshots)
* ImageMagick + oxipng (for optimizing snapshots) [optional but recommended]
* `PTPIMG_API_KEY` environment variable (for uploading snapshots)

## Supported trackers
Name           | Abbreviation | Server upload allowed
-------------- | ------------ | -------------------------------------------------------------------
AvistaZ        | `avz`        | :white_check_mark: Yes, if added as seedbox in profile
BroadcasTheNet | `btn`        | :warning: Dedicated servers only, requires staff approval
HDBits         | `hdb`        | :white_check_mark: Yes, if IP whitelisted in profile or 2FA enabled

## Usage
Place cookies in `~/.local/share/pymkt/cookies/TRACKER.txt` where `TRACKER` is the 3-letter code of the tracker above
(all lowercase).

If you need to use a proxy (because you're uploading from a server for example),
you can define it in `~/.config/pymkt/config.yml` (see `config.yml.example` for the format).

```
$ ./mkt.py -t tracker1,tracker2,tracker3 FILE_OR_FOLDER
```
Options:
* `--auto`: Skip prompts to confirm autofilled data is correct and upload fully automatically
  (unless we're unable to infer some info without user input)
* `--short`: Temporary hack for files shorter than 20 minutes (5 minutes for full seasons),
  takes screenshots at 1/2/3/4 minutes rather than 5/10/15/20. Eventually duration will be
  auto-detected.
* `--snapshots`: Override number of snapshots to take (default: 4).

## Notes
Movie support is not fully implemented yet. Only tested with TV shows.
