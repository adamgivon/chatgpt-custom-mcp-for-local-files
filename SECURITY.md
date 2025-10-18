# Security Guidelines

Best practices for keeping your MCP server secure.

---

## Table of Contents

1. [Threat Model](#threat-model)
2. [File System Security](#file-system-security)
3. [OAuth Security](#oauth-security)
4. [Network Security](#network-security)
5. [Secrets Management](#secrets-management)
6. [Monitoring and Auditing](#monitoring-and-auditing)
7. [Security Checklist](#security-checklist)

---

## Threat Model

### What This Setup Protects Against

**Unauthorized access to your files:**

OAuth 2.0 prevents random internet users from accessing your server. Only ChatGPT with valid credentials can connect.

**Network eavesdropping:**

Cloudflare Tunnel provides TLS encryption. All traffic between ChatGPT and your server is encrypted.

**Directory traversal attacks:**

Server validates all file paths. ChatGPT cannot access files outside BASE_DIR.

**Token theft:**

Tokens expire after 24 hours. Even if stolen, limited time window for abuse.

### What This Setup Does NOT Protect Against

**Compromised ChatGPT account:**

If someone logs into your ChatGPT account, they can access your files. Use strong ChatGPT password and 2FA.

**Malicious files in BASE_DIR:**

ChatGPT reads whatever you put in BASE_DIR. Don't put sensitive files you don't want ChatGPT to see.

**Server compromise:**

If your machine is compromised, attacker has full access. Keep your system updated and secure.

**OpenAI data retention:**

ChatGPT may retain file contents for model training per OpenAI's policies. Review OpenAI's privacy policy.

---

## File System Security

### Choose BASE_DIR Carefully

**Only expose what ChatGPT needs:**

Don't set BASE_DIR to your home directory or root:

```bash
# BAD - Exposes everything
BASE_DIR=/home/username

# BAD - Exposes system files
BASE_DIR=/

# GOOD - Dedicated folder
BASE_DIR=/home/username/mcp-files
```

**Create dedicated folder:**

```bash
mkdir ~/mcp-files
chmod 755 ~/mcp-files
```

**Copy files you want to share:**

Don't symlink to sensitive locations:

```bash
# BAD - Links to sensitive folder
ln -s ~/Documents ~/mcp-files/docs

# GOOD - Copy specific files
cp ~/Documents/public-doc.pdf ~/mcp-files/
```

### File Permissions

**Server runs as your user:**

It can read any file your user can read.

**Restrict permissions on sensitive files:**

```bash
# Files in BASE_DIR
chmod 644 ~/mcp-files/*

# BASE_DIR itself
chmod 755 ~/mcp-files
```

**Check what's exposed:**

```bash
ls -la ~/mcp-files
```

Review regularly. Remove files when no longer needed.

### Path Traversal Protection

**Server validates all paths:**

```python
def safe_path(rel_path: str) -> Path:
    p = (BASE_DIR / rel_path).resolve()
    if not str(p).startswith(str(BASE_DIR)):
        raise ValueError("Invalid path")
    return p
```

This prevents:
- `../../../etc/passwd`
- Absolute paths like `/etc/passwd`
- Symlinks pointing outside BASE_DIR

**Do not modify this function** unless you understand the security implications.

---

## OAuth Security

### Client Credentials

**Generate strong secrets:**

```bash
openssl rand -hex 32
```

Never use predictable values:

```bash
# BAD
OAUTH_CLIENT_SECRET=password123

# BAD
OAUTH_CLIENT_SECRET=chatgpt-secret

# GOOD
OAUTH_CLIENT_SECRET=a7f3e9d24b8c1f5e2a9d3b6c8f1e4a7b...
```

**Keep secrets private:**

Never commit .env to git:

```bash
# Add to .gitignore
echo ".env" >> .gitignore
```

Never share secrets in public channels.

### Token Expiration

**Tokens expire after 24 hours:**

```python
expires_in = 86400  # 24 hours
```

This limits damage if token is stolen.

**Tokens stored in memory only:**

```python
oauth_tokens = {}  # Lost on server restart
```

Server restart invalidates all tokens.

**Registered clients persist:**

```python
# Saved to oauth_clients.json
registered_clients = {...}
```

Protect this file:

```bash
chmod 600 oauth_clients.json
```

### Revoking Access

**Delete registered client:**

```bash
# View clients
cat oauth_clients.json

# Remove specific client
# Edit file and remove client entry

# Or delete all
rm oauth_clients.json
```

Restart server. All clients must re-register.

**In ChatGPT:**

Settings → Apps and Connectors → Your Connector → Delete

This removes stored credentials from ChatGPT.

---

## Network Security

### Cloudflare Tunnel Benefits

**No open ports:**

No need to forward ports on router. Server not directly exposed to internet.

**DDoS protection:**

Cloudflare provides automatic DDoS mitigation.

**TLS encryption:**

All traffic encrypted end-to-end.

**Cloudflare as reverse proxy:**

Cloudflare sits between internet and your server. Hides your real IP address.

### Tunnel Credentials Security

**Credentials stored in:**

```
~/.cloudflared/TUNNEL_ID.json
```

**Protect this file:**

```bash
chmod 600 ~/.cloudflared/*.json
```

Anyone with this file can run your tunnel.

**Don't share tunnel credentials:**

Each user should create their own tunnel.

### HTTPS Only

**Always use HTTPS:**

```
https://mcp.yourdomain.com  # Good
http://mcp.yourdomain.com   # Bad - Not encrypted
```

Cloudflare automatically provides HTTPS.

**Verify in browser:**

Visit your URL. Check for padlock icon.

---

## Secrets Management

### Environment Variables

**Never hardcode secrets:**

```python
# BAD
OAUTH_CLIENT_SECRET = "my-secret"

# GOOD
OAUTH_CLIENT_SECRET = os.getenv("OAUTH_CLIENT_SECRET")
```

**Use .env file:**

```bash
cp .env.example .env
nano .env
```

**Protect .env:**

```bash
chmod 600 .env
echo ".env" >> .gitignore
```

### Rotating Secrets

**When to rotate:**

- Suspected compromise
- Employee/collaborator leaves
- Regular schedule (every 6-12 months)

**How to rotate:**

1. Generate new secret:

```bash
openssl rand -hex 32
```

2. Update .env:

```bash
nano .env
# Change OAUTH_CLIENT_SECRET
```

3. Restart server:

```bash
systemctl --user restart mcp-server
```

4. Delete registered clients:

```bash
rm oauth_clients.json
```

5. Reconnect ChatGPT (deletes old connector, creates new)

### Backup Security

**If backing up config:**

Never include .env or oauth_clients.json in public backups.

```bash
# Backup safely
tar -czf mcp-backup.tar.gz \
  --exclude=.env \
  --exclude=oauth_clients.json \
  --exclude=venv \
  ~/chatgpt-custom-mcp-for-local-files
```

---

## Monitoring and Auditing

### Server Logs

**Check who's accessing:**

```bash
# View recent activity
journalctl --user -u mcp-server -n 100

# Watch in real-time
journalctl --user -u mcp-server -f
```

Look for:
- Successful tool calls
- Failed authentication attempts
- Unusual access patterns

### Registered Clients

**Review periodically:**

```bash
cat oauth_clients.json | jq
```

Check:
- How many clients registered
- When they were created
- Do you recognize them all

**Remove unknown clients:**

Edit oauth_clients.json and remove unknown entries.

### File Access Audit

**Log file reads:**

Modify server_mcp.py to log accessed files:

```python
def read_file_content(rel_path: str, limit_bytes: int = 20000) -> str:
    logger.info(f"File accessed: {rel_path}")
    # ... rest of function
```

Restart server. Check logs to see what ChatGPT reads.

### Failed Authentication

**Watch for repeated failures:**

```bash
journalctl --user -u mcp-server | grep "Invalid"
```

Many failures may indicate attack attempt.

**Rate limiting (optional):**

Add rate limiting to OAuth endpoints if concerned:

```python
from slowapi import Limiter

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

@app.post("/oauth/token")
@limiter.limit("10/minute")
async def oauth_token(...):
```

Requires `pip install slowapi`.

---

## Security Checklist

### Initial Setup

- [ ] Strong OAUTH_CLIENT_SECRET generated
- [ ] BASE_DIR contains only intended files
- [ ] .env file protected (chmod 600)
- [ ] .env added to .gitignore
- [ ] Tunnel credentials protected
- [ ] Server running as non-root user
- [ ] HTTPS working (padlock in browser)

### Regular Maintenance

- [ ] Review files in BASE_DIR monthly
- [ ] Check registered clients quarterly
- [ ] Review server logs for anomalies
- [ ] Update dependencies when available
- [ ] Rotate secrets annually
- [ ] Keep system and packages updated

### If Compromise Suspected

- [ ] Stop services immediately
- [ ] Check server logs for unauthorized access
- [ ] Rotate all secrets
- [ ] Delete oauth_clients.json
- [ ] Review files in BASE_DIR for changes
- [ ] Reconnect ChatGPT with new credentials
- [ ] Consider reporting to security team

---

## Support

This project is provided as-is with no support or maintenance guarantees.

If you encounter issues:
- Review the documentation carefully
- Check existing GitHub issues (read-only)
- Fork and modify for your needs

No support requests will be answered.
---

## Additional Resources

**OAuth 2.0 Security Best Practices:**

https://tools.ietf.org/html/rfc6819

**Cloudflare Tunnel Security:**

https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/

**Python Security:**

https://python.readthedocs.io/en/stable/library/security_warnings.html

**File System Security:**

https://wiki.archlinux.org/title/File_permissions_and_attributes

---

**Remember:** Security is a process, not a destination. Stay vigilant and keep your system updated.
