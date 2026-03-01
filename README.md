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

### Step 1 — Build the tar.gz

The integration must be compiled for aarch64 (the remote's CPU). The easiest way is to use the included GitHub Actions workflow:

1. Create a new **public or private GitHub repository**
2. Push this project to it
3. Go to **Actions** → **Build and Release** → **Run workflow**
4. Once complete, download the `uc-intg-memcardpro-aarch64` artifact
5. Extract the zip — inside is `uc-intg-memcardpro-dev-aarch64.tar.gz`

> **Alternatively**, tag a release (`git tag v1.0.0 && git push --tags`) and the workflow will automatically create a GitHub Release with the tar.gz attached.

### Step 2 — Upload to the Remote

1. Open your remote's web interface at `http://your-remote-ip`
2. Go to **Integrations** → **Add new** → **Install custom**
3. Select the `uc-intg-memcardpro-*-aarch64.tar.gz` file
4. Wait for the upload to complete

### Step 3 — Setup

1. The integration will appear in your integrations list — click it and select **Start setup**
2. Enter the **IP address or hostname** of your MemCard PRO (e.g. `192.168.1.100`)
3. Give it a friendly **name** (e.g. `PS2 MemCard PRO`)
4. Repeat the setup for each additional MemCard PRO device

---

## Notes

- The MemCard PRO uses **HTTPS with a self-signed certificate** — the integration ignores certificate errors, which is safe for local network use
- If your MemCard PROs are on a different subnet (e.g. an IoT VLAN), ensure the remote can reach the devices on port 443
- Each device gets its own media player entity on the remote

## Building Locally (Advanced)

If you have Docker installed and want to build locally:

```bash
# Install QEMU for aarch64 emulation (Linux only)
sudo apt install qemu binfmt-support qemu-user-static

# Build
docker run --rm \
  --platform=aarch64 \
  --user=$(id -u):$(id -g) \
  -v "$PWD":/workspace \
  docker.io/unfoldedcircle/r2-pyinstaller:3.11.13 \
  bash -c \
    "cd /workspace && \
     python -m pip install --user -r requirements.txt && \
     PYTHON_VERSION=\$(python --version | cut -d' ' -f2 | cut -d. -f1,2) && \
     PYTHONPATH=~/.local/lib/python\${PYTHON_VERSION}/site-packages:\$PYTHONPATH \
     pyinstaller --clean --onedir --name intg-memcardpro \
       --collect-all zeroconf \
       intg-memcardpro/driver.py"

# Package
mkdir -p artifacts/bin
cp -r dist/intg-memcardpro/* artifacts/bin/
mv artifacts/bin/intg-memcardpro artifacts/bin/driver
cp driver.json artifacts/
tar czvf uc-intg-memcardpro-aarch64.tar.gz -C artifacts .
```
