# Secure MCP server with OAuth 2.0 for ChatGPT
# Compatible with ChatGPT Developer Mode (JSON-RPC over HTTP)

import os
import json
import logging
import secrets
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta

from fastapi import FastAPI, Request, Response, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from dotenv import load_dotenv

# ---- Load env ----
load_dotenv()
OAUTH_CLIENT_ID = os.getenv("OAUTH_CLIENT_ID", "chatgpt-mcp-default")
OAUTH_CLIENT_SECRET = os.getenv("OAUTH_CLIENT_SECRET", "change-this-secret")
BASE_DIR_STR = os.getenv("BASE_DIR", "./files")

# ---- Paths ----
BASE_DIR = Path(BASE_DIR_STR).resolve()
CLIENTS_DB = Path("./oauth_clients.json").resolve()

# ---- Constants ----
PROTOCOL_VERSION = "2024-05-30"
SERVER_NAME = "mcp-docreader"
SERVER_VERSION = "1.0.5-oauth"

ALLOWED_ORIGINS = [
    "https://chatgpt.com",
    "https://chat.openai.com",
    "*"
]

# ---- In-memory OAuth storage ----
oauth_codes = {}  # code -> {client_id, expires}
oauth_tokens = {}  # token -> {expires}
registered_clients = {}  # client_id -> {client_secret, metadata}

# ---- Load persisted clients ----
def load_clients():
    if CLIENTS_DB.exists():
        try:
            with open(CLIENTS_DB, 'r') as f:
                data = json.load(f)
                # Convert ISO timestamps back to datetime
                for client_id, client_data in data.items():
                    client_data['created_at'] = datetime.fromisoformat(client_data['created_at'])
                    registered_clients[client_id] = client_data
                logger.info(f"Loaded {len(registered_clients)} registered clients")
        except Exception as e:
            logger.error(f"Failed to load clients: {e}")

def save_clients():
    try:
        # Convert datetime to ISO string for JSON
        data = {}
        for client_id, client_data in registered_clients.items():
            data[client_id] = {
                **client_data,
                'created_at': client_data['created_at'].isoformat()
            }
        with open(CLIENTS_DB, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save clients: {e}")

# ---- App ----
app = FastAPI(title="MCP Document Reader with OAuth", version=SERVER_VERSION)

@app.middleware("http")
async def add_protocol_header(request, call_next):
    response = await call_next(request)
    response.headers["MCP-Protocol-Version"] = PROTOCOL_VERSION
    response.headers["Server"] = f"mcp-docreader/{SERVER_VERSION}"
    return response

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

logger = logging.getLogger("uvicorn.error")

# ---- Load persisted clients after logger is ready ----
load_clients()

# =============== OAuth 2.0 Endpoints ===============

@app.get("/.well-known/oauth-authorization-server")
async def oauth_discovery(request: Request):
    """OAuth 2.0 metadata discovery"""
    base_url = str(request.base_url).rstrip('/')
    return {
        "issuer": base_url,
        "authorization_endpoint": f"{base_url}/oauth/authorize",
        "token_endpoint": f"{base_url}/oauth/token",
        "registration_endpoint": f"{base_url}/oauth/register",
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code", "client_credentials"],
        "token_endpoint_auth_methods_supported": ["client_secret_post", "client_secret_basic"],
    }

@app.get("/.well-known/oauth-protected-resource")
async def oauth_protected_resource(request: Request):
    """OAuth 2.0 Protected Resource metadata"""
    base_url = str(request.base_url).rstrip('/')
    return {
        "resource": base_url,
        "authorization_servers": [base_url],
        "bearer_methods_supported": ["header"],
        "resource_documentation": f"{base_url}",
    }

@app.get("/oauth/authorize")
async def oauth_authorize(
    client_id: str,
    redirect_uri: str,
    response_type: str = "code",
    state: Optional[str] = None,
    scope: Optional[str] = None
):
    """OAuth authorization endpoint"""
    # Check if client is registered dynamically or is the default
    if client_id != OAUTH_CLIENT_ID and client_id not in registered_clients:
        raise HTTPException(status_code=400, detail="Invalid client_id")
    
    if response_type != "code":
        raise HTTPException(status_code=400, detail="Unsupported response_type")
    
    # Generate authorization code
    code = secrets.token_urlsafe(32)
    oauth_codes[code] = {
        "client_id": client_id,
        "expires": datetime.now() + timedelta(minutes=10)
    }
    
    # Build redirect URL
    redirect_url = f"{redirect_uri}?code={code}"
    if state:
        redirect_url += f"&state={state}"
    
    logger.info(f"OAuth authorize: redirecting to {redirect_url}")
    return RedirectResponse(url=redirect_url, status_code=302)

@app.post("/oauth/token")
async def oauth_token(
    grant_type: str = Form(...),
    client_id: str = Form(...),
    client_secret: str = Form(...),
    code: Optional[str] = Form(None),
    redirect_uri: Optional[str] = Form(None)
):
    """OAuth token endpoint"""
    # Check if client is registered or is the default
    valid_secret = None
    if client_id == OAUTH_CLIENT_ID:
        valid_secret = OAUTH_CLIENT_SECRET
    elif client_id in registered_clients:
        valid_secret = registered_clients[client_id]["client_secret"]
    else:
        logger.warning(f"Unknown client_id: {client_id}")
        raise HTTPException(status_code=401, detail="Invalid client credentials")
    
    # Validate client secret
    if client_secret != valid_secret:
        logger.warning(f"Invalid client secret for: {client_id}")
        raise HTTPException(status_code=401, detail="Invalid client credentials")
    
    if grant_type == "authorization_code":
        if not code:
            raise HTTPException(status_code=400, detail="Missing code")
        
        if code not in oauth_codes:
            raise HTTPException(status_code=400, detail="Invalid code")
        
        code_data = oauth_codes[code]
        
        # Check expiry
        if code_data["expires"] < datetime.now():
            del oauth_codes[code]
            raise HTTPException(status_code=400, detail="Code expired")
        
        # Check client match
        if code_data["client_id"] != client_id:
            raise HTTPException(status_code=400, detail="Client mismatch")
        
        # Remove used code
        del oauth_codes[code]
    
    elif grant_type == "client_credentials":
        # Direct client credentials - ok
        pass
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported grant_type: {grant_type}")
    
    # Generate access token
    access_token = secrets.token_urlsafe(48)
    expires_in = 86400  # 24 hours
    
    oauth_tokens[access_token] = {
        "expires": datetime.now() + timedelta(seconds=expires_in)
    }
    
    logger.info(f"OAuth token issued: {access_token[:16]}...")
    
    return {
        "access_token": access_token,
        "token_type": "Bearer",
        "expires_in": expires_in,
    }

@app.post("/oauth/register")
async def oauth_register(request: Request):
    """RFC 7591 Dynamic Client Registration"""
    try:
        body = await request.json()
    except:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    
    # Generate client credentials
    client_id = f"chatgpt-{secrets.token_urlsafe(16)}"
    client_secret = secrets.token_urlsafe(48)
    
    # Store client metadata
    registered_clients[client_id] = {
        "client_secret": client_secret,
        "redirect_uris": body.get("redirect_uris", []),
        "client_name": body.get("client_name", "ChatGPT MCP"),
        "created_at": datetime.now()
    }
    
    # Persist to disk
    save_clients()
    
    logger.info(f"Registered new client: {client_id}")
    
    # Return client credentials per RFC 7591
    return {
        "client_id": client_id,
        "client_secret": client_secret,
        "client_id_issued_at": int(datetime.now().timestamp()),
        "client_secret_expires_at": 0,  # Never expires
        "redirect_uris": body.get("redirect_uris", []),
        "token_endpoint_auth_method": "client_secret_post",
        "grant_types": ["authorization_code", "client_credentials"],
        "response_types": ["code"]
    }

# =============== Auth Validation ===============

def verify_oauth_token(req: Request):
    """Verify OAuth Bearer token"""
    auth_header = req.headers.get("Authorization", "")
    
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")
    
    token = auth_header.split(" ", 1)[1].strip()
    
    if token not in oauth_tokens:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    # Check expiry
    if oauth_tokens[token]["expires"] < datetime.now():
        del oauth_tokens[token]
        raise HTTPException(status_code=401, detail="Token expired")

# =============== Models ===============

class JSONRPCRequest(BaseModel):
    jsonrpc: str
    method: str
    params: Optional[Dict[str, Any]] = None
    id: Optional[Any] = None

def jsonrpc_response(id_val: Any, result: Any = None, error: Dict[str, Any] = None) -> Dict[str, Any]:
    resp = {"jsonrpc": "2.0", "id": id_val}
    if error:
        resp["error"] = error
    else:
        resp["result"] = result
    return resp

# =============== File Operations ===============

def safe_path(rel_path: str) -> Path:
    """Prevent directory traversal"""
    p = (BASE_DIR / rel_path).resolve()
    if not str(p).startswith(str(BASE_DIR)):
        raise ValueError("Invalid path")
    return p

def list_files(base: Path = BASE_DIR, max_depth: int = 999) -> List[Dict[str, Any]]:
    """Recursively list files"""
    items = []
    for root, dirs, files in os.walk(base):
        depth = len(Path(root).relative_to(base).parts)
        if depth > max_depth:
            continue
        for f in files:
            full = Path(root) / f
            rel = full.relative_to(BASE_DIR)
            items.append({
                "id": str(rel),
                "name": f,
                "path": str(rel),
                "size": full.stat().st_size,
                "type": "code" if full.suffix in {".py", ".js", ".java", ".cpp", ".html", ".css"} else "document"
            })
    return items

def read_file_content(rel_path: str, limit_bytes: int = 20000) -> str:
    """Safely read file content"""
    p = safe_path(rel_path)
    if not p.exists() or not p.is_file():
        raise FileNotFoundError(f"File not found: {rel_path}")
    with open(p, "r", encoding="utf-8", errors="ignore") as f:
        return f.read(limit_bytes)

# =============== MCP Tools ===============

def mcp_tools_list() -> Dict[str, Any]:
    """Advertise tools"""
    return {
        "tools": [
            {
                "name": "search",
                "title": "Search Files",
                "description": "Search for files by name substring",
                "inputSchema": {
                    "type": "object",
                    "properties": {"query": {"type": "string", "description": "Substring to search for"}},
                    "required": ["query"],
                },
            },
            {
                "name": "fetch",
                "title": "Fetch File",
                "description": "Retrieve file content by ID (path)",
                "inputSchema": {
                    "type": "object",
                    "properties": {"id": {"type": "string", "description": "Relative file path"}},
                    "required": ["id"],
                },
            },
            {
                "name": "list_files",
                "title": "List Files",
                "description": "List local documents and code files",
                "inputSchema": {
                    "type": "object",
                    "properties": {"depth": {"type": "integer", "default": 2}},
                    "required": [],
                },
            },
            {
                "name": "read_file",
                "title": "Read File",
                "description": "Read content of a document or code file",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Relative path of file"},
                        "limit_bytes": {"type": "integer", "default": 20000},
                    },
                    "required": ["path"],
                },
            },
        ]
    }

def tool_call_list_files(params: Dict[str, Any]) -> Dict[str, Any]:
    depth = int(params.get("depth", 2))
    files = list_files(BASE_DIR, depth)
    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps({"files": files}, indent=2)
            }
        ]
    }

def tool_call_read_file(params: Dict[str, Any]) -> Dict[str, Any]:
    rel = params.get("path")
    if not rel:
        return {
            "content": [{"type": "text", "text": "Error: Missing path"}],
            "isError": True
        }
    try:
        content = read_file_content(rel, params.get("limit_bytes", 20000))
        return {
            "content": [
                {
                    "type": "text",
                    "text": content
                }
            ]
        }
    except Exception as e:
        return {
            "content": [{"type": "text", "text": f"Error: {str(e)}"}],
            "isError": True
        }

def tool_call_search(params: Dict[str, Any]) -> Dict[str, Any]:
    query = params.get("query", "").lower()
    all_files = list_files(BASE_DIR, 3)
    results = [f for f in all_files if query in f["name"].lower()]
    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps({"results": results}, indent=2)
            }
        ]
    }

def tool_call_fetch(params: Dict[str, Any]) -> Dict[str, Any]:
    file_id = params.get("id")
    if not file_id:
        return {
            "content": [{"type": "text", "text": "Error: Missing id"}],
            "isError": True
        }
    return tool_call_read_file({"path": file_id})

# =============== Main JSON-RPC Handler ===============

@app.post("/")
async def mcp_root(req: Request) -> Response:
    # Verify OAuth token for all MCP requests
    verify_oauth_token(req)
    
    try:
        payload = await req.json()
    except Exception:
        return Response(
            content=json.dumps(jsonrpc_response(None, error={"code": -32700, "message": "Parse error"})),
            media_type="application/json",
            status_code=400,
        )

    if isinstance(payload, list):
        responses = [await handle_rpc_one(JSONRPCRequest(**item)) for item in payload]
        return Response(content=json.dumps(responses), media_type="application/json")

    rpc = JSONRPCRequest(**payload)
    resp_obj = await handle_rpc_one(rpc)
    return Response(content=json.dumps(resp_obj), media_type="application/json")

async def handle_rpc_one(rpc: JSONRPCRequest) -> Dict[str, Any]:
    method = rpc.method
    params = rpc.params or {}
    id_val = rpc.id
    
    logger.info(f"RPC method: {method}, params: {params}")

    try:
        if method == "initialize":
            return jsonrpc_response(id_val, {
                "protocolVersion": params.get("protocolVersion", PROTOCOL_VERSION),
                "capabilities": {
                    "tools": {"listChanged": False},
                    "resources": {},
                    "prompts": {}
                },
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            })

        if method == "initialized":
            return jsonrpc_response(id_val, {"ok": True})
        
        if method == "notifications/initialized":
            return jsonrpc_response(id_val, {"ok": True})

        if method == "tools/list":
            return jsonrpc_response(id_val, mcp_tools_list())

        if method == "tools/call":
            tool_name = params.get("name")
            args = params.get("arguments", {}) or {}

            if tool_name == "list_files":
                return jsonrpc_response(id_val, tool_call_list_files(args))
            if tool_name == "read_file":
                return jsonrpc_response(id_val, tool_call_read_file(args))
            if tool_name == "search":
                return jsonrpc_response(id_val, tool_call_search(args))
            if tool_name == "fetch":
                return jsonrpc_response(id_val, tool_call_fetch(args))

            return jsonrpc_response(id_val, error={"code": -32601, "message": f"Unknown tool: {tool_name}"})

        if method == "search":
            return jsonrpc_response(id_val, tool_call_search(params))

        if method == "fetch":
            return jsonrpc_response(id_val, tool_call_fetch(params))

        return jsonrpc_response(id_val, error={"code": -32601, "message": f"Unknown method: {method}"})

    except Exception as e:
        logger.exception("RPC error")
        return jsonrpc_response(id_val, error={"code": -32000, "message": str(e)})

# =============== Health Endpoints ===============

@app.get("/")
async def health():
    return {
        "status": "running",
        "oauth": "enabled",
        "root": str(BASE_DIR),
        "protocol": PROTOCOL_VERSION
    }

@app.get("/sse")
@app.post("/sse")
async def sse_stub():
    return Response(status_code=204)

# =============== Entrypoint ===============

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server_mcp:app", host="0.0.0.0", port=4000)