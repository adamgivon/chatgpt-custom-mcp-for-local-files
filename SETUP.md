# Complete Setup Guide

This guide walks you through setting up the MCP server from scratch.

---

## Table of Contents

1. [System Requirements](#system-requirements)
2. [Python Environment Setup](#python-environment-setup)
3. [Cloudflare Account Setup](#cloudflare-account-setup)
4. [Cloudflare Tunnel Setup](#cloudflare-tunnel-setup)
5. [MCP Server Configuration](#mcp-server-configuration)
6. [Testing the Setup](#testing-the-setup)
7. [ChatGPT Integration](#chatgpt-integration)
8. [Optional: systemd Services](#optional-systemd-services)
9. [Optional: Desktop Launchers](#optional-desktop-launchers)

---

## System Requirements

**Operating System:**

- Linux (Ubuntu 20.04+, Debian 11+, or similar)
- macOS (10.15+)
- Windows with WSL2

**Software:**

- Python 3.8 or higher
- pip (Python package manager)
- curl or wget
- Text editor (nano, vim, Kate or VS Code)

**Network:**

- Internet connection
- Domain name (can be free subdomain from Cloudflare)
- No port forwarding required

**Accounts:**

- Cloudflare account (free tier works)
- ChatGPT Plus or Pro subscription

---

## Python Environment Setup

### 1. Check Python Version

```bash
python3 --version
```

Should show Python 3.8 or higher.

If not installed:

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install python3 python3-pip python3-venv
```

**macOS:**
```bash
brew install python3
```

### 2. Clone Repository

```bash
cd ~
git clone https://github.com/adamgivon/chatgpt-custom-mcp-for-local-files.git
cd chatgpt-custom-mcp-for-local-files
```

### 3. Create Virtual Environment (in /chatgpt-custom-mcp-for-local-files - all actions (venv+tunnel+server etc. will take place in this folder))

```bash
python3 -m venv venv
```

### 4. Activate Virtual Environment

**Linux/macOS:**
```bash
source venv/bin/activate
```

**Windows (WSL):**
```bash
source venv/bin/activate
```

Your prompt should now show `(venv)`.

### 5. Install Dependencies

```bash
pip install -r requirements.txt
```

This installs FastAPI, Uvicorn, Pydantic, and python-dotenv.

Verify installation:

```bash
pip list
```

Should show fastapi, uvicorn, pydantic, python-dotenv.

---

## Cloudflare Account Setup

### 1. Create Cloudflare Account

Go to https://dash.cloudflare.com/sign-up

Sign up with email. Free tier is sufficient.

### 2. Add Your Domain

**Best way - own a domain**

Click "Add a site". Enter your domain. Follow the nameserver (DNS) change instructions from your original domain registrar to cloudflare ones.


### 3. Enable Zero Trust (Free)

Go to https://one.dash.cloudflare.com/

Select your account. Click "Zero Trust" in sidebar.

Choose a team name (e.g., "my-mcp-server").

Select Free plan.

---

## Cloudflare Tunnel Setup

### 1. Install cloudflared

**Ubuntu/Debian:**

```bash
curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb -o cloudflared.deb
sudo dpkg -i cloudflared.deb
```

**macOS:**

```bash
brew install cloudflare/cloudflare/cloudflared
```

**Other Linux:**

```bash
curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -o cloudflared
chmod +x cloudflared
sudo mv cloudflared /usr/local/bin/
```

Verify installation:

```bash
cloudflared --version
```

### 2. Authenticate cloudflared

```bash
cloudflared tunnel login
```

This opens a browser. Select your Cloudflare account and domain. Grants cloudflared access to your account.

### 3. Create Tunnel

```bash
cloudflared tunnel create mcp-files
```

Output shows:

```
Created tunnel mcp-files with id XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX
```

Save this tunnel ID. You'll need it.

Credentials saved to: `~/.cloudflared/TUNNEL_ID.json`

### 4. Configure DNS

Go to Cloudflare Dashboard → Your Domain → DNS → Records

Add CNAME record:

```
Type: CNAME
Name: mcp
Target: TUNNEL_ID.cfargotunnel.com
Proxy: Yes (orange cloud)
TTL: Auto
```

Replace `TUNNEL_ID` with your actual tunnel ID from step 3.

This makes your server accessible at `https://mcp.yourdomain.com`

### 5. Create Tunnel Configuration

```bash
mkdir -p ~/.cloudflared
nano ~/.cloudflared/config.yml
```

Add this content:

```yaml
tunnel: YOUR_TUNNEL_ID
credentials-file: /home/YOUR_USERNAME/.cloudflared/YOUR_TUNNEL_ID.json

ingress:
  - hostname: mcp.yourdomain.com
    service: http://localhost:4000
  - service: http_status:404
```

Replace:
- `YOUR_TUNNEL_ID` with your actual tunnel ID
- `YOUR_USERNAME` with your system username
- `mcp.yourdomain.com` with your actual domain

Save and exit (Ctrl+O, Enter, Ctrl+X in nano).

### 6. Test Tunnel

```bash
cloudflared tunnel run mcp-files
```

Should show:

```
Connection registered
```

Leave this running. Open a NEW TERMINAL (!!) for next steps.

---

## MCP Server Configuration

### 1. Create Files Directory

Choose where to store files ChatGPT will access:

```bash
mkdir -p ~/mcp-files
```

Add some test files:

```bash
echo "This is a test file" > ~/mcp-files/test.txt
echo "# Hello World" > ~/mcp-files/README.md
```

### 2. Configure Environment

In the repository directory:

```bash
cp .env.example .env
nano .env
```

Edit these values:

```bash
BASE_DIR=/home/YOUR_USERNAME/mcp-files
OAUTH_CLIENT_ID=chatgpt-mcp-default
OAUTH_CLIENT_SECRET=PASTE_RANDOM_STRING_HERE
```

Generate secure secret:

```bash
openssl rand -hex 32
```

Copy the output and paste as `OAUTH_CLIENT_SECRET`.

Replace `YOUR_USERNAME` with your actual username.

Save and exit.

### 3. Start MCP Server

Make sure virtual environment is activated:

```bash
source venv/bin/activate
```

Start server:

```bash
python server_mcp.py
```

Should show:

```
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:4000
```

Server is now running.

---

## Testing the Setup

### 1. Test Server Locally

Open new terminal:

```bash
curl http://localhost:4000/
```

Should return:

```json
{"status":"running","oauth":"enabled","root":"...","protocol":"2024-05-30"}
```

### 2. Test Through Tunnel

```bash
curl https://mcp.yourdomain.com/
```

Should return same JSON response.

If it fails, check:
- Tunnel is running
- DNS record is correct
- Server is running

### 3. Test OAuth Discovery

```bash
curl https://mcp.yourdomain.com/.well-known/oauth-authorization-server
```

Should return OAuth metadata with endpoints.

If all tests pass, setup is complete!

---

## ChatGPT Integration

### 1. Enable Developer Mode

Go to https://chatgpt.com

Click your profile (bottom left) → Settings → Apps and Connectors

Enable "Developer Mode"

### 2. Create Custom Connector

Go to: Apps and Connectors → Enabled Connectors → Create

Fill in:

```
Name: Local Files
URL: https://mcp.yourdomain.com
OAuth: Yes
```

Click "Create"

### 3. Authorization Flow

ChatGPT will:
1. Register with your server (dynamic client registration)
2. Redirect you for authorization
3. Exchange code for access token
4. Store credentials

This happens automatically.

You should see "Connected" status.

### 4. Test in ChatGPT

Start a new chat.

Click paperclip icon → Select "Local Files"

Try: "List all files you can access"

ChatGPT should show files from your `~/mcp-files` directory.

Try: "Read the test.txt file"

ChatGPT should show the content.

Success! ChatGPT can now access your local files.

---

## Optional: systemd Services

For automatic startup on Linux.

### 1. Create Service Files

**MCP Server Service:**

```bash
mkdir -p ~/.config/systemd/user
nano ~/.config/systemd/user/mcp-server.service
```

Content:

```ini
[Unit]
Description=MCP File Server
After=network.target

[Service]
Type=simple
WorkingDirectory=/home/YOUR_USERNAME/chatgpt-custom-mcp-for-local-files
ExecStart=/home/YOUR_USERNAME/chatgpt-custom-mcp-for-local-files/venv/bin/python /home/YOUR_USERNAME/chatgpt-custom-mcp-for-local-files/server_mcp.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
```

Replace `YOUR_USERNAME` with your actual username.

**Tunnel Service:**

```bash
nano ~/.config/systemd/user/mcp-tunnel.service
```

Content:

```ini
[Unit]
Description=Cloudflare Tunnel for MCP
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/cloudflared tunnel run mcp-files
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
```

### 2. Enable Services

```bash
systemctl --user daemon-reload
systemctl --user enable mcp-server mcp-tunnel
systemctl --user start mcp-server mcp-tunnel
```

### 3. Check Status

```bash
systemctl --user status mcp-server
systemctl --user status mcp-tunnel
```

Both should show "active (running)".

### 4. View Logs

```bash
journalctl --user -u mcp-server -f
journalctl --user -u mcp-tunnel -f
```

Services now start automatically on boot.

---

## Optional: Desktop Launchers

For Linux desktop environments (KDE, GNOME, etc).

### 1. Create Start Launcher

```bash
nano ~/.local/share/applications/mcp-start.desktop
```

Content:

```ini
[Desktop Entry]
Type=Application
Name=Start MCP Server
Comment=Start Cloudflare Tunnel and MCP Server
Exec=bash -c "systemctl --user start mcp-server mcp-tunnel && zenity --info --text='MCP Services Started' --timeout=2"
Icon=emblem-default
Terminal=false
Categories=Utility;Network;
```

### 2. Create Stop Launcher

```bash
nano ~/.local/share/applications/mcp-stop.desktop
```

Content:

```ini
[Desktop Entry]
Type=Application
Name=Stop MCP Server
Comment=Stop Cloudflare Tunnel and MCP Server
Exec=bash -c "systemctl --user stop mcp-server mcp-tunnel && zenity --info --text='MCP Services Stopped' --timeout=2"
Icon=emblem-pause
Terminal=false
Categories=Utility;Network;
```

### 3. Make Executable

```bash
chmod +x ~/.local/share/applications/mcp-*.desktop
```

### 4. Update Database

```bash
update-desktop-database ~/.local/share/applications/
```

Now search for "Start MCP Server" or "Stop MCP Server" in your application menu.

---

## Next Steps

Setup complete! You can now:

- Add more files to your `BASE_DIR` folder
- Use ChatGPT to explore and read your files
- Check server logs for debugging
- Read SECURITY.md for security best practices
- Read TROUBLESHOOTING.md if issues arise

For questions or issues, see the GitHub repository.
