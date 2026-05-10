import os
import re
import logging
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, field_validator, model_validator
import docker
import uvicorn

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CADDYFILE_PATH = os.getenv("CADDYFILE_PATH", "/caddyfile/Caddyfile")
CADDY_CONTAINER = os.getenv("CADDY_CONTAINER", "caddy")
CADDY_CONFIG_PATH = os.getenv("CADDY_CONFIG_PATH", "/etc/caddy/Caddyfile")
PORT = int(os.getenv("PORT", "5000"))
SELF_HOSTNAME = os.getenv("SELF_HOSTNAME", "")
CADDY_CERT_PATH = os.getenv("CADDY_CERT_PATH", "/caddydata/pki/authorities/local/root.crt")

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="Caddy GUI", version="1.0.0")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


class ServiceEntry(BaseModel):
    domain: str
    type: str
    backend: str

    @field_validator("domain")
    @classmethod
    def validate_domain(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Domain cannot be empty")
        if re.search(r"[\s{}\\\n\r]", v):
            raise ValueError("Domain contains invalid characters (no spaces, braces, or backslashes)")
        if not re.match(r"^[a-zA-Z0-9*][a-zA-Z0-9.\-*:]*$", v):
            raise ValueError("Invalid domain format")
        return v

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        if v not in ("proxy", "https_proxy", "redirect"):
            raise ValueError("Type must be one of: proxy, https_proxy, redirect")
        return v

    @model_validator(mode="after")
    def validate_backend(self) -> "ServiceEntry":
        v = self.backend.strip() if self.backend else ""
        if not v:
            raise ValueError("Backend cannot be empty")
        if self.type == "redirect":
            clean = v.replace("{uri}", "")
            if re.search(r"[{}\\\n\r]", clean):
                raise ValueError("Backend contains invalid characters")
        else:
            if re.search(r"[{}\\\n\r]", v):
                raise ValueError("Backend contains invalid characters")
        self.backend = v
        return self


# ── Caddyfile parser ──────────────────────────────────────────────────────────

def _read_block(content: str, pos: int) -> tuple[str, int]:
    """Read a brace-delimited block starting at pos (must be '{')."""
    assert content[pos] == "{"
    start = pos
    depth = 0
    while pos < len(content):
        ch = content[pos]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                pos += 1
                return content[start:pos], pos
        pos += 1
    return content[start:pos], pos


def parse_caddyfile(content: str) -> tuple[str, list[dict]]:
    """Return (global_block_str, list_of_service_dicts)."""
    pos = 0
    length = len(content)
    global_block = ""
    entries: list[dict] = []

    def skip_ws():
        nonlocal pos
        while pos < length and content[pos] in " \t\n\r":
            pos += 1

    def skip_line():
        nonlocal pos
        while pos < length and content[pos] != "\n":
            pos += 1

    skip_ws()

    # Global block starts with a bare '{' (no preceding domain token)
    if pos < length and content[pos] == "{":
        global_block, pos = _read_block(content, pos)

    while pos < length:
        skip_ws()
        if pos >= length:
            break

        # Skip comment lines
        if content[pos] == "#":
            skip_line()
            continue

        # Read domain token (until whitespace or '{')
        domain_start = pos
        while pos < length and content[pos] not in " \t\n\r{":
            pos += 1
        domain = content[domain_start:pos].strip()

        skip_ws()

        if pos >= length or content[pos] != "{":
            skip_line()
            continue

        block, pos = _read_block(content, pos)

        if domain:
            entry = _parse_block(domain, block)
            if entry:
                entries.append(entry)

    return global_block, entries


def _parse_block(domain: str, block_content: str) -> Optional[dict]:
    inner = block_content.strip()
    if inner.startswith("{"):
        inner = inner[1:]
    if inner.endswith("}"):
        inner = inner[:-1]
    inner = inner.strip()

    # Redirect
    redir_match = re.search(r"redir\s+(\S+)", inner)
    if redir_match:
        target = redir_match.group(1)
        backend = target.replace("{uri}", "").rstrip("/")
        return {"domain": domain, "type": "redirect", "backend": backend}

    # HTTPS proxy with TLS skip verify
    if "tls_insecure_skip_verify" in inner:
        m = re.search(r"reverse_proxy\s+(https://\S+?)(?=\s|\{|$)", inner)
        if not m:
            m = re.search(r"reverse_proxy\s+(https://\S+)", inner)
        if m:
            return {"domain": domain, "type": "https_proxy", "backend": m.group(1)}

    # Simple reverse proxy
    m = re.search(r"reverse_proxy\s+(\S+)", inner)
    if m:
        backend = m.group(1)
        if backend.startswith("https://"):
            return {"domain": domain, "type": "https_proxy", "backend": backend}
        return {"domain": domain, "type": "proxy", "backend": backend}

    return None


def _generate_block(entry: dict) -> str:
    domain = entry["domain"]
    backend = entry["backend"]
    etype = entry["type"]

    if etype == "proxy":
        return f"{domain} {{\n    reverse_proxy {backend}\n}}"

    if etype == "https_proxy":
        if not backend.startswith("https://"):
            backend = f"https://{backend}"
        return (
            f"{domain} {{\n"
            f"    reverse_proxy {backend} {{\n"
            f"        transport http {{\n"
            f"            tls_insecure_skip_verify\n"
            f"        }}\n"
            f"    }}\n"
            f"}}"
        )

    if etype == "redirect":
        target = backend if "{uri}" in backend else f"{backend}{{uri}}"
        return f"{domain} {{\n    redir {target}\n}}"

    return ""


def read_caddyfile() -> tuple[str, list[dict]]:
    path = Path(CADDYFILE_PATH)
    if not path.exists():
        logger.warning("Caddyfile not found at %s", CADDYFILE_PATH)
        return "", []
    return parse_caddyfile(path.read_text(encoding="utf-8"))


def write_caddyfile(global_block: str, entries: list[dict]) -> None:
    parts = [global_block.strip()] if global_block.strip() else []
    for entry in entries:
        block = _generate_block(entry)
        if block:
            parts.append(block)
    content = "\n\n".join(parts) + "\n"
    Path(CADDYFILE_PATH).write_text(content, encoding="utf-8")


def reload_caddy() -> None:
    try:
        client = docker.from_env()
    except docker.errors.DockerException as exc:
        raise RuntimeError(f"Cannot connect to Docker socket: {exc}") from exc

    try:
        container = client.containers.get(CADDY_CONTAINER)
    except docker.errors.NotFound:
        raise RuntimeError(f"Container '{CADDY_CONTAINER}' not found")

    result = container.exec_run(
        ["caddy", "reload", "--config", CADDY_CONFIG_PATH, "--adapter", "caddyfile"],
        demux=False,
    )
    if result.exit_code != 0:
        output = result.output.decode("utf-8", errors="replace") if result.output else ""
        raise RuntimeError(f"caddy reload failed (exit {result.exit_code}): {output}")

    logger.info("Caddy reloaded successfully")


def save_and_reload(global_block: str, entries: list[dict]) -> None:
    """Write new config and reload; restore old config on failure."""
    path = Path(CADDYFILE_PATH)
    old_content = path.read_text(encoding="utf-8") if path.exists() else None
    write_caddyfile(global_block, entries)
    try:
        reload_caddy()
    except Exception:
        if old_content is not None:
            path.write_text(old_content, encoding="utf-8")
        raise


# ── API routes ────────────────────────────────────────────────────────────────

@app.get("/", include_in_schema=False)
async def root():
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.get("/api/services")
async def get_services():
    try:
        global_block, entries = read_caddyfile()
        return {"services": entries, "self_hostname": SELF_HOSTNAME}
    except Exception as exc:
        logger.error("get_services error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/services", status_code=201)
async def add_service(entry: ServiceEntry):
    try:
        global_block, entries = read_caddyfile()
        if any(e["domain"] == entry.domain for e in entries):
            raise HTTPException(status_code=409, detail=f"Domain '{entry.domain}' already exists")
        entries.append(entry.model_dump())
        save_and_reload(global_block, entries)
        return {"status": "ok", "entry": entry.model_dump()}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("add_service error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@app.put("/api/services/{domain:path}")
async def update_service(domain: str, entry: ServiceEntry):
    try:
        global_block, entries = read_caddyfile()
        idx = next((i for i, e in enumerate(entries) if e["domain"] == domain), None)
        if idx is None:
            raise HTTPException(status_code=404, detail=f"Domain '{domain}' not found")
        if entry.domain != domain and any(e["domain"] == entry.domain for e in entries):
            raise HTTPException(status_code=409, detail=f"Domain '{entry.domain}' already exists")
        entries[idx] = entry.model_dump()
        save_and_reload(global_block, entries)
        return {"status": "ok", "entry": entry.model_dump()}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("update_service error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@app.delete("/api/services/{domain:path}")
async def delete_service(domain: str):
    try:
        global_block, entries = read_caddyfile()
        new_entries = [e for e in entries if e["domain"] != domain]
        if len(new_entries) == len(entries):
            raise HTTPException(status_code=404, detail=f"Domain '{domain}' not found")
        save_and_reload(global_block, new_entries)
        return {"status": "ok"}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("delete_service error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/cert/download")
async def download_cert():
    cert_path = Path(CADDY_CERT_PATH)
    if not cert_path.exists():
        raise HTTPException(status_code=404, detail=f"Certificate not found at {CADDY_CERT_PATH}")
    return FileResponse(
        path=str(cert_path),
        filename="caddy-root-ca.crt",
        media_type="application/x-x509-ca-cert",
    )


@app.get("/api/config")
async def get_config():
    return {"self_hostname": SELF_HOSTNAME, "caddy_container": CADDY_CONTAINER}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=PORT, reload=False)
