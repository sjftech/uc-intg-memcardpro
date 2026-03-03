# MemCard PRO — Unfolded Circle Remote 3 Integration

An integration driver for the [Unfolded Circle Remote 3](https://www.unfoldedcircle.com/) that displays the currently loaded game and cover art from [MemCard PRO](https://8bitmods.com) devices.

Supports all three MemCard PRO variants:

| Device | Console | Cover Art Source |
|---|---|---|
| MemCard PRO | PlayStation (PS1) | xlenore/psx-covers |
| MemCard PRO 2 | PlayStation 2 | xlenore/ps2-covers |
| MemCard PRO GC | GameCube | AppCakeLtd/gc-covers |

Cover art is looked up by game serial — no API key required.

## Features

- Shows current game title on the remote
- Displays cover art sourced from serial-based GitHub repos
- Supports multiple devices (add each one separately during setup)
- Polls every 10 seconds for the current game
- Runs directly on the UCR3 remote — no external server needed

---

## Installation

### Step 1 — Download the latest release

Go to the [Releases](../../releases/latest) page and download `uc-intg-memcardpro-*-aarch64.tar.gz`.

### Step 2 — Upload to the Remote

1. Open your remote's web interface at `http://your-remote-ip`
2. Go to **Integrations** → **Add new** → **Install custom**
3. Select the downloaded `uc-intg-memcardpro-*-aarch64.tar.gz` file
4. Wait for the upload to complete

### Step 3 — Setup

1. The integration will appear in your integrations list — click it and select **Start setup**
2. Enter the **IP address or hostname** of your MemCard PRO (e.g. `192.168.1.100`)
3. Give it a friendly **name** (e.g. `PS2 MemCard PRO`)
4. Repeat the setup for each additional MemCard PRO device

---

## Notes

- The MemCard PRO uses **HTTPS with a self-signed certificate** — the integration ignores certificate errors, which is safe for local network use
- If your MemCard PRO is on a different subnet (e.g. an IoT VLAN), ensure the remote can reach the device on port 443
- Each device gets its own media player entity on the remote
