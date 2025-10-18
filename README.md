# chatgpt.com-custom-mcp-for-local-files
Custom MCP server for reading local files using Cloudflare Tunnel. Point ChatGPT to a dedicated folder on your machine - the model reads complete files on demand. No RAG pre-processing, no partial reads, no uploads. Direct file access through secure OAuth 2.0.

Features
🔒 Secure OAuth 2.0 authentication with dynamic client registration (RFC 7591)
🌐 Cloudflare Tunnel for secure remote access without port forwarding
📁 Complete file access - ChatGPT reads entire files, not chunks
🔍 Smart file discovery - Search by name, list directories, read on demand
💾 Persistent sessions - Registered clients survive server restarts
🚀 systemd integration - Start/stop with system services
🖥️ Desktop launchers - GUI shortcuts for easy control (Linux)
Why This Over RAG?
Traditional RAG (Retrieval-Augmented Generation):

Requires preprocessing and embedding generation
Returns partial/chunked content
Adds latency and complexity
Limited context about file structure
This MCP Server:

Direct file system access
Reads complete files on demand
ChatGPT can explore your directory structure
Lower latency for small files
No preprocessing needed
Prerequisites
OS: Linux (tested on Ubuntu/Kubuntu), macOS, or Windows with WSL
Python: 3.8+
Cloudflare Account: Free tier works
Domain: Any domain managed by Cloudflare
ChatGPT: Plus or Pro account (for MCP support - must follow: settings -> Apps & connectors -> advanced settings -> on. Go back to Apps & connectors - > create (top page, right) )

Quick Start
1. Clone Repository
bash
git clone https://github.com/YOUR_USERNAME/chatgpt-custom-mcp-for-local-files.git
cd chatgpt-custom-mcp-for-local-files
2. Install Dependencies
bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
3. Configure Environment
bash
cp .env.example .env
nano .env  # Edit with your settings
Required variables:

BASE_DIR: Path to your files folder
OAUTH_CLIENT_ID: Generated automatically or set manually
OAUTH_CLIENT_SECRET: Generated automatically or set manually
4. Set Up Cloudflare Tunnel
See detailed setup guide for complete instructions.

bash
# Install cloudflared
# Create tunnel
cloudflared tunnel create mcp-files
# Configure DNS
# Start tunnel
cloudflared tunnel run mcp-files
5. Start MCP Server
bash
python server_mcp.py
6. Connect ChatGPT
Go to ChatGPT → Settings → Apps and Connectors → Developer Mode → Enable
Go to Enabled Connectors → Create
Fill in:
Name: Local Files
URL: https://your-domain.com
OAuth: Yes
ChatGPT will auto-register and authenticate
Architecture
┌─────────────┐      HTTPS       ┌──────────────────┐      Local      ┌──────────────┐
│   ChatGPT   │ ────────────────> │ Cloudflare Tunnel│ ──────────────> │  MCP Server  │
│             │   OAuth 2.0       │   (your-domain)  │   Port 4000     │ (localhost)  │
└─────────────┘                   └──────────────────┘                 └──────────────┘
                                                                              │
                                                                              ▼
                                                                        ┌──────────────┐
                                                                        │  Your Files  │
                                                                        │   Folder     │
                                                                        └──────────────┘
Available Tools
ChatGPT can use these MCP tools:

Tool	Description	Example Use
list_files	List all files in directory	"Show me all Python files"
read_file	Read complete file content	"Read the README.md"
search	Search files by name	"Find files containing 'config'"
fetch	Get file by path	"Fetch src/main.py"
Security Considerations
✅ OAuth 2.0 prevents unauthorized access
✅ Files never leave your machine (served on-demand)
✅ Cloudflare Tunnel encrypts all traffic
✅ No credentials stored in ChatGPT
⚠️ Only expose folders you want ChatGPT to access
⚠️ Review BASE_DIR carefully before starting
See SECURITY.md for detailed security guidelines.

Troubleshooting
ChatGPT shows "424 Failed Dependency"

Check server logs for actual error
Verify OAuth token is valid
Ensure MCP response format is correct
Tunnel connection fails

Verify DNS records point to tunnel
Check tunnel is running: cloudflared tunnel info
Review tunnel logs
Server won't start

Check port 4000 is available: lsof -i :4000
Verify Python dependencies installed
Check .env file exists with correct values
See TROUBLESHOOTING.md for complete guide.

systemd Setup (Linux)
For automatic startup and management:

bash
# Copy service files
cp setup/systemd/*.service ~/.config/systemd/user/

# Edit paths in service files
nano ~/.config/systemd/user/mcp-server.service

# Enable and start
systemctl --user daemon-reload
systemctl --user enable mcp-server mcp-tunnel
systemctl --user start mcp-server mcp-tunnel

# Check status
systemctl --user status mcp-server
Desktop Launchers (Linux)
bash
# Copy desktop files
cp setup/desktop/*.desktop ~/.local/share/applications/

# Update desktop database
update-desktop-database ~/.local/share/applications/

# Now "Start MCP Server" appears in your app menu
Project Structure
.
├── server_mcp.py              # Main MCP server
├── requirements.txt           # Python dependencies
├── .env.example              # Environment template
├── setup/
│   ├── tunnel-config.yml.example
│   └── systemd/
│       ├── mcp-server.service
│       └── mcp-tunnel.service
└── docs/
    ├── SETUP.md              # Detailed setup guide
    ├── TROUBLESHOOTING.md    # Common issues
    └── SECURITY.md           # Security best practices
Contributing
Contributions welcome! Please:

Fork the repository
Create a feature branch
Test your changes thoroughly
Submit a pull request
License
MIT License - see LICENSE file for details.

Acknowledgments
Built following the MCP Protocol Specification
Uses Cloudflare Tunnel for secure access
Implements RFC 7591 for dynamic client registration
Support
📖 Documentation
🐛 Report Issues
💬 Discussions
Note: This is an independent project and is not officially affiliated with OpenAI or Anthropic.

