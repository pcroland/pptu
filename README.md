# pymkt

Python torrent creator and auto-uploader

## Requirements
* Python 3.8+
* Python package dependencies (`poetry install` or `pip install .`)
* torrenttools (for creating torrents)
* MediaInfo CLI (for generating tech info)
* FFmpeg (for generating snapshots)

## Supported trackers
Name           | Abbreviation | Authentication method | Captcha | Server upload allowed
-------------- | ------------ | --------------------- | ------- |  -------------------------------------------------------------------
AvistaZ        | `AvZ`        | Credentials/Cookies   | Yes     | :white_check_mark: Yes, if added as seedbox in profile
BroadcasTheNet | `BTN`        | Credentials/Cookies   | No      | :warning: Dedicated servers only, requires staff approval
CinemaZ        | `CZ`         | Credentials/Cookies   | Yes     | :white_check_mark: Yes, if added as seedbox in profile
HDBits         | `HDB`        | Credentials/Cookies   | Simple  | :white_check_mark: Yes, if IP whitelisted in profile or 2FA enabled
PassThePopcorn | `PTP`        | Cookies               | N/A     | :warning: Dedicated servers only, requires staff approval
PrivateHD      | `PHD`        | Credentials/Cookies   | Yes     | :white_check_mark: Yes, if added as seedbox in profile

"Captcha: Yes" means 2captcha API key is required to solve the captcha.
"Simple" means there is a captcha but it can be solved automatically without 2captcha.

### AvistaZ Network (AvistaZ, CinemaZ, PrivateHD)
Using cookies is not recommended as they expire within a few days.

### BroadcasTheNet
selenium-wire and undetected-chromedriver are required for credential login to pass the Cloudflare challenge.
Note that headless mode does not work, so if you're running this on a headless server you'll need to enable X11 forwarding.

### HDBits
If you don't specify a TOTP secret in the config, 2FA code will be prompted for when cookies are missing or expired.
You can disable the prompt with `totp_secret = false` if your account doesn't have 2FA.

## Installation
Install dependencies and the script with `./install.sh`. You can re-run the script to update after a git pull.

## Setup
Copy `config.example.toml` to `~/.config/pymkt/config.toml` and edit it as appropriate.

For credential-based auth, add your credentials in `~/.config/pymkt/config.toml`:
```
[TRACKER]
username = "yourusername"
password = "yourpassword"
```
Optionally, you may specify `totp_secret` for automating 2FA logins.

For cookie-based auth, place cookies in `~/.local/share/pymkt/cookies/TRACKER.txt`.

`TRACKER` is the name or the abbreviation of the tracker above (all lowercase).

## Usage
```
$ mkt -t tracker1,tracker2,tracker3 FILE_OR_FOLDER
```
Options:
* `--auto`: Skip prompts to confirm autofilled data is correct and upload fully automatically
  (unless we're unable to infer some info without user input)
* `--snapshots`: Override number of snapshots to take (default: 4).

## Notes
Movie support for BTN is not yet implemented.
