# Changelog

All notable changes to **Caddy SuperSimple GUI** are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [1.0.0] — 2026-05-10

### Added

**Backend (`app/main.py`)**
- FastAPI application with Uvicorn serving on configurable `PORT` (default 5000)
- Caddyfile parser: character-level brace-balanced block reader that handles global blocks and three entry types (proxy, https_proxy, redirect)
- Global block preservation: the top-level `{ ... }` block is always read and written back verbatim
- `GET /api/services` — returns all parsed services and the configured `SELF_HOSTNAME`
- `POST /api/services` — validates and adds a new service entry
- `PUT /api/services/{domain}` — validates and replaces an existing entry (supports domain rename)
- `DELETE /api/services/{domain}` — removes a service entry
- `GET /api/cert/download` — serves the Caddy root CA certificate file
- `GET /api/config` — returns runtime configuration (self_hostname, caddy_container)
- Atomic save-and-reload: old Caddyfile content is restored if `caddy reload` fails
- Caddy reload via Docker socket using `container.exec_run()` (Python `docker` SDK)
- Pydantic v2 input validation with `field_validator` and `model_validator`
- Domain validator: blocks whitespace, curly braces, backslashes; enforces character-set pattern
- Backend validator: blocks `{}` and backslashes (allows `{uri}` for redirect type)

**Frontend (`app/static/index.html`)**
- Single-file SPA — no build step, no npm, no framework
- Dark mode by default; light mode toggle persisted in `localStorage`
- CSS custom properties for full theming with smooth transitions
- Multilingual UI via JSON files; active language persisted in `localStorage`
- Fallback to English for missing translation keys
- Service table with type badges (Proxy / HTTPS Proxy / Redirect) and colour-coded rows
- Add/Edit modal with per-type backend label, placeholder, and hint text
- Delete confirmation dialog
- Self-hostname entry marked with a "This app" chip
- Warning shown when editing the self-hostname entry
- Post-save redirect countdown (5 s) with automatic redirect when the GUI's own hostname changes
- Root CA certificate download button with informational card
- Toast notifications (success / error) with 4.5 s auto-dismiss
- Keyboard shortcuts: Enter to save in modal, Escape to close modal
- Backdrop click closes modals
- Event delegation for table row buttons (XSS-safe via `esc()` helper)
- Responsive layout: backend column hidden on small screens, type column hidden on very small screens

**Internationalisation**
- `app/static/i18n/en.json` — English (reference / fallback)
- `app/static/i18n/nl.json` — Dutch
- `app/static/i18n/de.json` — German

**DevOps / Docker**
- `Dockerfile`: `python:3.11-alpine` multi-arch base, installs dependencies, runs as non-root (`appuser`) by default
- `docker-compose.yml`: external Docker network reference, Docker socket mount, Caddyfile and data volume mounts, all config via env vars
- `.env.example`: documented reference for all environment variables
- `.gitignore`: Python, Docker, IDE, and Caddy runtime exclusions

**Documentation**
- `README.md`: vibe-coding notice, feature list, quick-start guide, env var table, multi-arch build instructions, language extension guide, security note
- `CLAUDE.md`: architecture reference, file map, API contract, env vars, frontend conventions, reload flow, known limitations
- `CHANGELOG.md`: this file

---

## [1.0.1] — 2026-05-10

### Changed

- `Dockerfile`: switched base image from `python:3.11-slim` to `python:3.11-alpine` for a smaller image footprint
- `Dockerfile`: updated non-root user creation to use Alpine-compatible commands (`addgroup -S` / `adduser -S -G`) instead of Debian/Ubuntu commands (`groupadd -r` / `useradd -r -g`)

---

## [1.0.2] — 2026-05-10

### Changed

- `docker-compose.yml`: removed `build: .` — the compose file is now production-only and pulls from the registry
- `docker-compose.yml`: image reference changed to `ghcr.io/bananenbaas/caddy-supersimple-gui:latest`

---

## [1.0.3] — 2026-05-10

### Added

- **Search input** in the services table toolbar — live client-side filtering by domain name as you type
- **Type filter dropdown** — filter table to All / Proxy / HTTPS Proxy / Redirect
- **Sortable column headers** — click Domain or Type to sort ascending; click again to sort descending; active sort column highlighted in the primary colour with a ↑/↓ indicator
- **Service count label** — shows "{visible} of {total} services" in the toolbar, updates live with filters
- `no_results` i18n key — distinct message when services exist but all are filtered out
- `filter_search_placeholder`, `filter_type_all`, `filter_count` i18n keys added to en/nl/de JSON files
- `t()` function now supports `{0}`, `{1}` … placeholder substitution

---

## [1.0.4] — 2026-05-10

### Fixed

- **Type-switch bug in Edit modal**: switching between Proxy / HTTPS Proxy / Redirect now correctly updates the backend field value:
  - → HTTPS Proxy: `https://` prefix is prepended automatically (strips any `http://` first)
  - → Proxy: `https://` / `http://` prefix is stripped, leaving bare `IP:Port`
  - → Redirect: `http://` is prepended if no protocol prefix is present; existing prefixes are kept

### Added

- **TLS Skip Verify indicator**: a green info strip appears below the backend field when type is HTTPS Proxy, confirming that `tls_insecure_skip_verify` will be written to the Caddyfile
- `adaptBackendForType(val, newType)` helper function handles all prefix transformations
- `tls_skip_verify_label` and `tls_auto_applied` i18n keys (EN / NL / DE)
- Updated `backend_placeholder_https_proxy` to show `https://` prefix in placeholder
- Updated `backend_hint_https_proxy` hint text to describe the automatic prefix behaviour

---

## [1.0.5] — 2026-05-10

### Added

- **Export Bookmarks** button in the toolbar (next to Download Root CA): generates and downloads `caddy-bookmarks.html` in Netscape Bookmark File Format
  - Root folder: "Caddy Services"
  - One sub-folder per service named after the full domain
  - Each folder contains one bookmark: `https://<domain>`
  - Generated entirely client-side in JavaScript from the current services list — no backend call
- `export_bookmarks` i18n key added to EN / NL / DE translation files

---

## [1.0.6] — 2026-05-10

### Fixed

- **Bookmark export structure**: subfolders are now grouped by domain suffix (e.g. all `.local` domains in a "local" folder, all `.internal` domains in an "internal" folder) instead of creating one folder per individual domain. Inside each suffix folder the bookmarks are a flat list — title = full domain, URL = `https://` + full domain. Suffix folders are sorted alphabetically.
- `data-i18n-placeholder` attribute support in `applyTranslations()` for translated input placeholders
