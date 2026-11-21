# SIlent-Keylogger

> **Warning:** This repository contains surveillance and persistence code that can capture keystrokes and clipboard content, hide its process window, and add itself to Windows startup. Use it only on devices you own or have explicit written authorization to test. Obtain informed consent, follow all applicable laws, and do not deploy it against third parties.

SIlent-Keylogger is a Python prototype for authorized Windows security research and user-consent demonstrations. It captures keyboard input with `pynput`, can monitor clipboard changes, batches logs, and sends them to a Discord webhook. The repository also includes a PyInstaller build configuration and a Flipper Zero BadUSB script for demonstration purposes.

## Project status

- **Version:** Prototype `v1.0`
- **Platform:** Windows 10/11 (primary); portions may run on Linux or macOS
- **Execution:** Python source or packaged Windows executable
- **Distribution:** The repository includes an example executable and a BadUSB download script
- **Maintenance status:** Experimental; APIs, filenames, configuration names, and build behavior may change

## Repository contents

| Path | Purpose |
|---|---|
| `keylogger/source/prototype.py` | Main Python prototype |
| `keylogger/source/prototype.spec` | PyInstaller specification for a windowed executable |
| `keylogger/source/dist/prototype.exe` | Prebuilt Windows executable |
| `keylogger/source/build/` | Generated PyInstaller build output |
| `badusb-download.txt` | Flipper Zero BadUSB demonstration script |

## Features

- Keyboard event capture via `pynput`
- Buffered keystrokes sent in configurable batches
- Optional clipboard-change monitoring
- Basic masking for email addresses, HTTP/HTTPS URLs, and Windows paths
- Local fallback log file (`keylog.txt`)
- Discord webhook delivery with retries and an optional fallback webhook
- Windows console hiding for packaged builds
- Optional Windows startup persistence
- PyInstaller configuration for creating a GUI-style executable

## Requirements

- Python 3.10 or newer
- Windows 10/11 for Windows persistence and console-hiding behavior
- Internet access to send data to Discord
- Python packages:
  - `pynput`
  - `requests`
  - `pyperclip` (optional, for clipboard monitoring)

## Installation

Run these commands inside an authorized test environment:

```bash
python -m venv .venv
```

Activate the environment:

```powershell
.\.venv\Scripts\Activate.ps1
```

Install dependencies:

```bash
python -m pip install --upgrade pip
pip install pynput requests pyperclip pyinstaller
```

## Configuration

Set environment variables before launching the source script:

| Variable | Default | Description |
|---|---:|---|
| `DISCORD_WEBHOOK` | None in documented configuration | Primary Discord webhook URL |
| `DISCORD_FALLBACK_WEBHOOK` | Empty | Optional secondary webhook used after primary delivery failure |
| `SEND_INTERVAL_SEC` | `60` | Seconds between batch deliveries |
| `MAX_KEYS_PER_MSG` | `200` | Maximum character count included in a Discord embed |
| `KEYLOG_LOG_FILE` | `keylog.txt` | Local fallback log path |

PowerShell example:

```powershell
$env:DISCORD_WEBHOOK = "https://discord.com/api/webhooks/YOUR_WEBHOOK_ID/YOUR_WEBHOOK_TOKEN"
$env:DISCORD_FALLBACK_WEBHOOK = ""
$env:SEND_INTERVAL_SEC = "60"
$env:MAX_KEYS_PER_MSG = "200"
$env:KEYLOG_LOG_FILE = "keylog.txt"
```

For a local-only test, leave `DISCORD_WEBHOOK` unset and use `--no-persistence`. The source will retain a local log when no webhook is available.

> Never commit a webhook URL or token to source control. Revoke any webhook that has been exposed and rotate it before reuse.

## Running the prototype

The script has an internal `main()` entry point and accepts the following flags:

```bash
python keylogger/source/prototype.py
```

Disable Windows startup persistence:

```bash
python keylogger/source/prototype.py --no-persistence
```

Hide the Windows console when running from an executable:

```bash
python keylogger/source/prototype.py --hide
```

Stop the source process with `Ctrl+C`. The final keyboard buffer is flushed before the process exits.

## Building a Windows executable

From the `keylogger/source` directory, build with the included specification:

```bash
pyinstaller prototype.spec
```

The output is written to `keylogger/source/dist/prototype.exe` by default. A build should be cryptographically identified and distributed only to explicitly authorized test machines.

## Security considerations

- Keyboard capture and clipboard monitoring can expose passwords, personal messages, financial information, and authentication codes.
- Basic regex masking is not a reliable guarantee of privacy and does not detect every sensitive value.
- Discord delivery may expose captured text to webhook holders and Discord infrastructure.
- Startup persistence changes the Windows registry under `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`.
- Console hiding and automatic startup are commonly associated with malicious behavior and may trigger endpoint protection or antivirus products.
- The `badusb-download.txt` script downloads and launches a payload and is not safe to execute as a normal setup procedure.
- The prebuilt executable should not be run or redistributed outside a controlled, authorized environment.

## Version history

### v1.0 prototype

- Initial keyboard capture implementation
- Discord webhook batching and retry logic
- Email, URL, and Windows-path masking
- Local file fallback logging
- Clipboard-change monitoring
- Windows console hiding
- Windows startup persistence
- PyInstaller executable build support
- Flipper Zero BadUSB deployment demonstration

## Responsible use

Before testing, document:

1. The devices and accounts in scope
2. Who has granted authorization
3. What data can be collected
4. How data is encrypted, stored, and deleted
5. The test start and end times
6. A rollback and incident-response procedure

Review applicable privacy, workplace, and computer-access laws before use. If this repository is intended for defensive training, prefer an isolated lab, synthetic input, and clearly visible consent controls.

## License

No license is currently included. All rights are reserved by the repository owner unless a license is explicitly added.
