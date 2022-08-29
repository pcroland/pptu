<p align="center"><img src="logo/logo.png" width="160" /><br />Python P2P Torrent Uploader</p>

## Requirements
* Python 3.8+
* Python package dependencies (`poetry install` or `pip install .`)
* torrenttools (for creating torrents)
* MediaInfo CLI (for generating tech info)
* FFmpeg (for generating snapshots)

## Supported trackers
<table>
  <tr>
    <th>Name</th>
    <th>Acronym</th>
    <th>Auth</th>
    <th>Cloudflare</th>
    <th>Captcha</th>
    <th>Server upload allowed</th>
  </tr>
  <tr>
    <th colspan="6">General</th>
  </tr>
  <tr>
    <th>BroadcasTheNet</th>
    <td align="center"><code>BTN</code></td>
    <td align="center">Credentials/<br />Cookies</td>
    <td align="center"><img src="https://github.githubassets.com/images/icons/emoji/unicode/2714.png" width="14" /> Yes</td>
    <td align="center"><img src="https://github.githubassets.com/images/icons/emoji/unicode/274c.png" width="14" /> No</td>
    <td><img src="https://github.githubassets.com/images/icons/emoji/unicode/26a0.png" width="14" /> Dedicated servers only, requires staff approval</td>
  </tr>
  <tr>
    <th>HDBits</th>
    <td align="center"><code>HDB</code></td>
    <td align="center">Credentials/<br />Cookies</td>
    <td align="center"><img width="14" src="https://github.githubassets.com/images/icons/emoji/unicode/274c.png"> No</td>
    <td align="center"><img width="14" src="https://github.githubassets.com/images/icons/emoji/unicode/2714.png"> Simple</td>
    <td><img src="https://github.githubassets.com/images/icons/emoji/unicode/2714.png" width="14" /> Yes, if IP whitelisted in profile or 2FA enabled</td>
  </tr>
  <tr>
    <th>PassThePopcorn</th>
    <td align="center"><code>PTP</code></td>
    <td align="center">Cookies</td>
    <td align="center">N/A</td>
    <td align="center">N/A</td>
    <td><img src="https://github.githubassets.com/images/icons/emoji/unicode/26a0.png" width="14" /> Dedicated servers only, requires staff approval</td>
  </tr>
  <tr>
    <th colspan="6">AvistaZ Network</th>
  </tr>
  <tr>
    <th>AvistaZ</td>
    <td align="center"><code>AvZ</code></td>
    <td align="center" rowspan="3">Credentials/<br />Cookies</td>
    <td align="center" rowspan="3"><img src="https://github.githubassets.com/images/icons/emoji/unicode/274c.png" width="14" /> No</td>
    <td align="center" rowspan="3"><img src="https://github.githubassets.com/images/icons/emoji/unicode/2714.png" width="14" /> Yes</td>
    <td rowspan="3"><img src="https://github.githubassets.com/images/icons/emoji/unicode/2714.png" width="14" /> Yes, if IP whitelisted in profile</td>
  </tr>
  <tr>
    <th>CinemaZ</th>
    <td align="center"><code>CZ</code></td>
  </tr>
  <tr>
    <th>PrivateHD</th>
    <td align="center"><code>PHD</code></td>
  </tr>
</table>

For sites with captcha, a 2captcha API key is required to solve the captcha. Manual solving may be added in the future.
"Simple" captchas can be solved automatically without 2captcha or user interaction.

### BroadcasTheNet
* selenium-wire and undetected-chromedriver are required for credential login to pass the Cloudflare challenge.
  You'll also need Xvfb on Linux as ChromeDriver's headless mode is detected by Cloudflare.
* Movie support is not yet implemented.

### AvistaZ Network
* Using credential auth is strongly recommended as cookies always expire within a few days.

## Installation
Install dependencies and the script with `./install.sh`. You can re-run the script to update after a git pull.

## Setup
Copy `config.example.toml` to `~/.config/pptu/config.toml` and edit it as appropriate.

For credential-based auth, add your credentials in `~/.config/pptu/config.toml`:
```
[TRACKER]
username = "yourusername"
password = "yourpassword"
```
Optionally, you may specify `totp_secret` for automating 2FA logins.

For cookie-based auth, place cookies in `~/.local/share/pptu/cookies/TRACKER.txt`.

`TRACKER` is the name or the abbreviation of the tracker above (all lowercase).

## Usage
```
❯ pptu -h
pptu 2022.08.29.1

USAGE: pptu [-h] [-v] -t ABBREV [-a] [-s] file

POSITIONAL ARGUMENTS:
  file                   files/directories to create torrents for

FLAGS:
  -h, --help             show this help message and exit
  -v, --version          show version and exit
  -t, --trackers ABBREV  tracker(s) to upload torrents to (required)
  -a, --auto             upload without confirmation
  -s, --skip-upload      skip upload
```
