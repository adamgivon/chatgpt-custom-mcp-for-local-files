# Troubleshooting Guide

Common issues and their solutions.

---

## Table of Contents

1. [Server Issues](#server-issues)
2. [Tunnel Issues](#tunnel-issues)
3. [OAuth Issues](#oauth-issues)
4. [ChatGPT Connection Issues](#chatgpt-connection-issues)
5. [File Access Issues](#file-access-issues)
6. [systemd Service Issues](#systemd-service-issues)

---

## Server Issues

### Server Won't Start

**Symptom:** Error when running `python server_mcp.py`

**Check 1: Port Already in Use**

```bash
lsof -i :4000
```

If something is using port 4000:

```bash
# Kill the process
kill -9 PID

# Or change server port in server_mcp.py (last line)
uvicorn.run("server_mcp:app", host="0.0.0.0", port=4001)
```

**Check 2: Missing Dependencies**

```bash
source venv/bin/activate
pip install -r requirements.txt
```

**Check 3: Python Version**

```bash
python3 --version
```

Must be 3.8 or higher.

**Check 4: .env File Missing**

```bash
ls -la .env
```

If missing:

```bash
cp .env.example .env
nano .env
```

### Server Crashes Immediately

**Check logs for error messages:**

```bash
python server_mcp.py
```

**Common errors:**

**"No module named 'fastapi'"**

Virtual environment not activated:

```bash
source venv/bin/activate
pip install -r requirements.txt
```

**"Permission denied" on BASE_DIR**

Check folder permissions:

```bash
ls -ld ~/mcp-files
chmod 755 ~/mcp-files
```

**"File not found: oauth_clients.json"**

Normal on first run. File is created automatically when first client registers.

### Server Runs But Returns Errors

**Test health endpoint:**

```bash
curl http://localhost:4000/
```

Should return JSON with status "running".

**If returns error:**

Check server logs for exception details.

Check BASE_DIR path is correct in .env file.

---

## Tunnel Issues

### Tunnel Won't Start

**Symptom:** Error when running `cloudflared tunnel run mcp-files`

**Check 1: Tunnel Exists**

```bash
cloudflared tunnel list
```

Should show "mcp-files" tunnel.

If not listed:

```bash
cloudflared tunnel create mcp-files
```

**Check 2: Config File Correct**

```bash
cat ~/.cloudflared/config.yml
```

Verify:
- Tunnel ID matches your actual tunnel ID
- Credentials file path is correct
- Hostname matches your DNS record
- Service points to http://localhost:4000

**Check 3: Credentials File Exists**

```bash
ls ~/.cloudflared/*.json
```

Should show your tunnel credentials file.

If missing, recreate tunnel:

```bash
cloudflared tunnel delete mcp-files
cloudflared tunnel create mcp-files
```

### Tunnel Starts But Connection Fails

**Check DNS records in Cloudflare:**

Go to Cloudflare Dashboard → DNS → Records

Verify CNAME record:
- Name: mcp (or your subdomain)
- Target: TUNNEL_ID.cfargotunnel.com
- Proxy: Enabled (orange cloud)

**DNS propagation:**

Wait 5-10 minutes for DNS changes to propagate.

Check DNS:

```bash
nslookup mcp.yourdomain.com
```

Should return Cloudflare IPs.

**Test tunnel connectivity:**

```bash
curl https://mcp.yourdomain.com/
```

If timeout: DNS not propagated yet or tunnel not running.

If 502 Bad Gateway: Tunnel running but server not running.

If 404: Wrong path in tunnel config.

### Tunnel Disconnects Frequently

**Check network stability:**

Tunnel requires stable internet connection.

**Check system resources:**

```bash
top
```

If CPU/memory maxed, tunnel may disconnect.

**View tunnel logs:**

```bash
cloudflared tunnel run mcp-files --loglevel debug
```

Look for connection errors or timeouts.

---

## OAuth Issues

### ChatGPT Shows "Invalid Client"

**Server didn't register the client properly.**

Check server logs when ChatGPT tries to connect.

Should see:

```
INFO: Registered new client: chatgpt-XXXXX
```

If not appearing:

**Check OAuth endpoints:**

```bash
curl https://mcp.yourdomain.com/.well-known/oauth-authorization-server
```

Should return OAuth metadata.

**Restart server and try again:**

```bash
# Stop server (Ctrl+C)
python server_mcp.py
```

In ChatGPT, delete and recreate the connector.

### Token Expired Errors

**Symptom:** ChatGPT works, then stops with 401 errors

**Tokens expire after 24 hours.**

ChatGPT should automatically request new token.

If it doesn't:

1. Delete connector in ChatGPT settings
2. Recreate connector
3. Reconnect

**If server restarted:**

Tokens are stored in memory and lost on restart.

ChatGPT will get 401 and request new token automatically.

Just wait 30 seconds and try again.

### Registered Clients Lost After Restart

**Check oauth_clients.json exists:**

```bash
ls -la oauth_clients.json
```

Should be in project directory.

**If missing:**

Registration persistence failed.

Check file permissions:

```bash
chmod 644 oauth_clients.json
```

Check disk space:

```bash
df -h
```

---

## ChatGPT Connection Issues

### Error Creating Connector

**"Server doesn't support RFC 7591"**

OAuth registration endpoint not working.

Test manually:

```bash
curl -X POST https://mcp.yourdomain.com/oauth/register \
  -H "Content-Type: application/json" \
  -d '{"client_name":"Test"}'
```

Should return client_id and client_secret.

If error: Check server logs for exception.

**"Connection timeout"**

Tunnel or server not running.

Check both are active:

```bash
# Check server
curl http://localhost:4000/

# Check tunnel
curl https://mcp.yourdomain.com/
```

### Connector Shows "Connected" But No Tools

**Check ChatGPT can reach tools endpoint:**

Look at server logs when using ChatGPT.

Should see:

```
INFO: RPC method: initialize
INFO: RPC method: tools/list
```

If only seeing "initialize" but not "tools/list":

ChatGPT didn't discover tools.

**Fix: Update protocol version response**

In server_mcp.py, ensure initialize returns:

```python
"protocolVersion": params.get("protocolVersion", PROTOCOL_VERSION)
```

This accepts ChatGPT's protocol version.

Restart server and reconnect.

### 424 Failed Dependency Error

**Symptom:** ChatGPT says "424" when calling tools

**This means response format is wrong.**

Check server logs for actual error in tool execution.

**Common causes:**

**Wrong response format:**

Tool responses must be:

```python
{
    "content": [
        {
            "type": "text",
            "text": "actual content here"
        }
    ]
}
```

Not:

```python
{"result": "content"}  # Wrong!
```

**Exception in tool execution:**

Check server logs for Python exceptions.

Fix the exception and restart server.

---

## File Access Issues

### ChatGPT Can't See Files

**Check BASE_DIR is correct:**

```bash
echo $BASE_DIR  # From .env
ls -la ~/mcp-files  # Check files exist
```

**Test list_files locally:**

```bash
# Get token first
curl -X POST https://mcp.yourdomain.com/oauth/token \
  -d "grant_type=client_credentials" \
  -d "client_id=chatgpt-mcp-default" \
  -d "client_secret=YOUR_SECRET" | jq -r .access_token

# Use token to list files
curl -X POST https://mcp.yourdomain.com/ \
  -H "Authorization: Bearer TOKEN_HERE" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"list_files","arguments":{}},"id":1}'
```

Should return file list.

If empty: BASE_DIR path is wrong.

If error: Check file permissions.

### Permission Denied Errors

**Server can't read files.**

Check file permissions:

```bash
ls -la ~/mcp-files
```

Files should be readable by your user:

```bash
chmod -R 644 ~/mcp-files/*
chmod 755 ~/mcp-files
```

### File Content Truncated

**By design: Files limited to 20000 bytes by default.**

To read more:

Ask ChatGPT: "Read the first 50000 bytes of file.txt"

This passes `limit_bytes: 50000` parameter.

Or modify default in server_mcp.py:

```python
def read_file_content(rel_path: str, limit_bytes: int = 100000):
```

---

## systemd Service Issues

### Service Won't Start

**Check service status:**

```bash
systemctl --user status mcp-server
systemctl --user status mcp-tunnel
```

Look for error messages.

**Common issues:**

**"Failed to start" - ExecStart path wrong**

Edit service file:

```bash
nano ~/.config/systemd/user/mcp-server.service
```

Verify paths are absolute and correct.

Reload:

```bash
systemctl --user daemon-reload
systemctl --user restart mcp-server
```

**"Permission denied"**

Service can't access files.

Check file ownership:

```bash
ls -la ~/chatgpt-custom-mcp-for-local-files
```

Should be owned by your user.

### Service Starts But Stops Immediately

**Check logs:**

```bash
journalctl --user -u mcp-server -n 50
```

Look for Python errors or exceptions.

Fix the error and restart:

```bash
systemctl --user restart mcp-server
```

### Service Doesn't Start on Boot

**Enable the service:**

```bash
systemctl --user enable mcp-server
systemctl --user enable mcp-tunnel
```

**Enable linger (allows user services to run without login):**

```bash
sudo loginctl enable-linger $USER
```

Reboot and verify:

```bash
systemctl --user status mcp-server
```

---

## General Debugging Tips

### Enable Detailed Logging

**Server logs:**

Run server directly (not via systemd):

```bash
python server_mcp.py
```

Watch output for errors.

**Tunnel logs:**

```bash
cloudflared tunnel run mcp-files --loglevel debug
```

Shows detailed connection info.

### Check All Components

**Quick health check:**

```bash
# 1. Server
curl http://localhost:4000/

# 2. Tunnel
curl https://mcp.yourdomain.com/

# 3. OAuth
curl https://mcp.yourdomain.com/.well-known/oauth-authorization-server

# 4. Tools
# (requires token - see File Access Issues above)
```

All should return successful responses.

### Reset Everything

**If nothing works, clean restart:**

```bash
# Stop services
systemctl --user stop mcp-server mcp-tunnel

# Or kill processes
pkill -f server_mcp
pkill -f cloudflared

# Delete registered clients
rm oauth_clients.json

# Restart server
python server_mcp.py

# In new terminal, restart tunnel
cloudflared tunnel run mcp-files

# In ChatGPT: delete and recreate connector
```

## Support

This project is provided as-is with no support or maintenance guarantees.

If you encounter issues:
- Review the documentation carefully
- Check existing GitHub issues (read-only)
- Fork and modify for your needs

No support requests will be answered.
---
