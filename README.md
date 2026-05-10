# Caddy SuperSimple GUI

> ⚠️ **VIBE CODING PROJECT** ⚠️
>
> This project was entirely generated through AI-assisted "vibe coding" — a specification was written in natural language and the full codebase was produced by Claude (Anthropic). No traditional engineering process was followed. Use in production at your own risk. Contributions and fixes are welcome.

A minimal, self-hosted web UI for managing a Caddyfile. No authentication — designed to run internally on a trusted local network alongside your existing Caddy stack.

---

## Features

- **View** all configured services in a clean table with type badges (Proxy / HTTPS Proxy / Redirect)
- **Add / Edit / Delete** services via a modal form
- **Three entry types** supported:
  - Simple reverse proxy: `reverse_proxy 192.168.1.10:8080`
  - HTTPS backend with TLS skip-verify: full `transport http { tls_insecure_skip_verify }` block
  - Redirect: `redir http://target{uri}`
- **Auto-reload**: after every change the Caddyfile is saved and `caddy reload` is executed inside the Caddy container via the Docker socket
- **Global block preserved**: the `{ ... }` global options block at the top of your Caddyfile is never touched
- **Self-hostname awareness**: marks its own Caddyfile entry and warns before you change it; redirects you automatically after save
- **Root CA download**: download Caddy's local CA certificate to install on client devices
- **Multilingual**: English, Dutch, German (add more by dropping a JSON file)
- **Dark / Light mode**: CSS-variable theming, persisted in `localStorage`
- **Multi-arch Docker image**: `linux/amd64` + `linux/arm/v7` — based on `python:3.11-alpine` for a minimal footprint

---

## Quick Start

### Prerequisites

- Docker & Docker Compose
- An existing Caddy container on a known Docker network

### 1. Clone

```bash
git clone <repo-url> caddy-gui
cd caddy-gui
```

### 2. Configure

```bash
cp .env.example .env
$EDITOR .env   # set your paths and container name
```

Key variables:

| Variable | Default | Description |
|---|---|---|
| `CADDYFILE_DIR` | `./caddyfile` | Host directory containing your Caddyfile |
| `CADDY_DATA_DIR` | `./caddydata` | Host path to Caddy's data directory (for root CA) |
| `CADDY_CONTAINER` | `caddy` | Name of your Caddy Docker container |
| `CADDY_CONFIG_PATH` | `/etc/caddy/Caddyfile` | Caddyfile path **inside** the Caddy container |
| `PORT` | `5000` | Port the GUI listens on |
| `SELF_HOSTNAME` | _(empty)_ | Hostname this GUI is served at (optional, enables self-aware mode) |
| `CADDY_NETWORK` | `caddy` | Name of the external Docker network |

### 3. Ensure the Docker network exists

```bash
docker network create caddy   # skip if it already exists
```

### 4. Start

```bash
docker compose up -d
```

The GUI is now reachable at `http://localhost:5000` (or via whatever hostname you configured in Caddy).

---

## Caddyfile requirements

Your Caddyfile should have the standard global block at the top:

```
{
    # global options — untouched by the GUI
    local_certs
    email you@example.com
}

service.example.local {
    reverse_proxy 192.168.1.10:8080
}
```

The GUI container mounts the same Caddyfile directory as your Caddy container so both see the same file.

---

## Root CA Certificate

When Caddy uses `local_certs`, it creates its own CA. To make browsers trust Caddy's HTTPS certificates:

1. Click **Download Root CA** in the GUI
2. Install `caddy-root-ca.crt` on each client device:
   - **Windows**: double-click → install to "Trusted Root Certification Authorities"
   - **macOS**: Keychain Access → import → set to "Always Trust"
   - **Linux**: copy to `/usr/local/share/ca-certificates/` → `sudo update-ca-certificates`
   - **Android/iOS**: open the file from your browser and follow the prompts

---

## Multi-arch build

The production image is published to the GitHub Container Registry:

```
ghcr.io/bananenbaas/caddy-supersimple-gui:latest
```

`docker compose up -d` pulls it automatically. To build and push a new image yourself:

```bash
docker buildx create --use
docker buildx build \
  --platform linux/amd64,linux/arm/v7 \
  -t ghcr.io/bananenbaas/caddy-supersimple-gui:latest \
  --push .
```

---

## Adding a language

1. Copy `app/static/i18n/en.json` → `app/static/i18n/xx.json`
2. Translate the values (keep the keys identical)
3. Add an `<option value="xx">` entry in the `#lang-select` dropdown in `app/static/index.html`
4. Rebuild or restart the container — no backend changes needed

---

## Project structure

```
caddy-supersimple-gui/
├── Dockerfile
├── docker-compose.yml
├── .env.example
├── .gitignore
├── README.md
├── CLAUDE.md
├── CHANGELOG.md
└── app/
    ├── main.py            # FastAPI backend
    ├── requirements.txt
    └── static/
        ├── index.html     # Single-page frontend
        └── i18n/
            ├── en.json
            ├── nl.json
            └── de.json
```

---

## Security note

This tool has **no authentication**. Run it only on a trusted internal network, behind a firewall, or restricted to a VPN. Do not expose it to the public internet.

---

## License

MIT — do whatever you want, but don't blame anyone if things break. This is a vibe project.
