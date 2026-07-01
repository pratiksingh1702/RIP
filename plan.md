# RIP Distribution Plan: `pip install rip` + `rip.exe`

## Goal
Ship RIP through two channels only:
1. **`pip install rip`** — for users who already have Python.
2. **A single standalone `.exe`** (portable or installer-wrapped) — for users who don't.

No thin-installer, no first-run dependency downloader, no bootstrap layer, no flag files. `pip`'s resolver already does the "defer heavy deps" job; a frozen `.exe` should just ship at its real size.

---

## 0. Guiding Decisions (do not revisit without reason)

| Decision | Reasoning |
|---|---|
| No custom bootstrap/first-run installer | ML deps (torch, transformers) are needed by nearly every real command (`repo index`), so there's nothing meaningful to defer. Deferred download just moves the pain to first command, mid-trust, with worse failure modes. |
| Use `torch` CPU-only wheel | Cuts ~750MB → ~150MB with no functional loss for local/offline inference. |
| `.exe` is honestly large (~500–600MB) | No attempt to hide size; disclosed upfront on the download page. |
| pip is the primary/recommended channel | Correct, resumable, cached, trusted dependency mechanism — reinvents nothing. |
| `.exe` build tool: PyInstaller `--onefile` | Simplest reliable option for this dependency set; revisit Nuitka only if AV false-positives become a real problem. |

---

## 1. Package for `pip install rip`

### 1.1 `pyproject.toml`
- [ ] Confirm `[project]` metadata: `name = "rip"` (check PyPI name availability — may need `rip-cli` or similar if taken), `version`, `description`, `readme`, `license`, `requires-python = ">=3.11"`.
- [ ] Add CLI entry point:
  ```toml
  [project.scripts]
  repo = "rip.cli:app"
  ```
- [ ] Split dependencies into groups:
  ```toml
  [project]
  dependencies = [
      "typer",
      "rich",
      "pydantic",
      "pydantic-settings",
      "gitpython",
      "httpx",
      "structlog",
      "tiktoken",
      "orjson",
      "python-dotenv",
      "tomli-w",
      "watchdog",
      "mcp",
      # core local-mode ML/search deps
      "torch",              # pinned to CPU wheel via index config, see 1.2
      "sentence-transformers",
      "transformers",
      "onnxruntime",
      "tree-sitter-language-pack",
      "optimum",
      "numpy",
      "scipy",
  ]

  [project.optional-dependencies]
  server = [
      "fastapi",
      "uvicorn[standard]",
      "neo4j",
      "qdrant-client",
      "sqlalchemy",
      "alembic",
      "asyncpg",
      "redis",
      "litellm",
  ]
  dev = [
      "pytest",
      "ruff",
      "mypy",
  ]
  ```
- [ ] Decide: are `neo4j`/`qdrant`/`fastapi` etc. **only** needed for server mode? If yes, keep them out of the base install — local-mode users (the default/primary audience) should not pull in Docker-oriented deps they'll never use. This alone likely saves 100+MB for most users.
- [ ] Document install variants in README:
  - `pip install rip` — local mode only
  - `pip install rip[server]` — adds server-mode deps

### 1.2 CPU-only torch
- [ ] Add explicit index/constraint so default install pulls CPU wheels, not CUDA:
  ```toml
  [tool.uv.sources]
  torch = { index = "pytorch-cpu" }

  [[tool.uv.index]]
  name = "pytorch-cpu"
  url = "https://download.pytorch.org/whl/cpu"
  explicit = true
  ```
  (If not using `uv`, document the equivalent `pip install torch --index-url https://download.pytorch.org/whl/cpu` instruction, or use `torch` extras that resolve to CPU build automatically.)
- [ ] Verify `sentence-transformers` and `transformers` still function correctly against CPU-only torch in local mode.

### 1.3 Build & Publish
- [ ] `pip install build twine` (or `uv build` / `uv publish`).
- [ ] Build: `python -m build` → produces `dist/*.whl` and `dist/*.tar.gz`.
- [ ] Test install locally in a clean venv: `pip install dist/rip-*.whl` then run `repo --help`.
- [ ] Publish to Test PyPI first: `twine upload --repository testpypi dist/*`.
- [ ] Verify install from Test PyPI in a fresh venv.
- [ ] Publish to real PyPI: `twine upload dist/*`.
- [ ] Confirm `pip install rip` works end-to-end from a clean machine/container.

### 1.4 Ongoing releases
- [ ] Set up a version-bump + build + publish step in CI (GitHub Actions) triggered on tag push (e.g. `v1.2.0`).
- [ ] Add a `CHANGELOG.md`.

---

## 2. Package for `rip.exe`

### 2.1 Prep
- [ ] Confirm target: **portable single-file exe** (no install wizard) for v1. Installer wrapper (PATH, shortcuts, uninstaller) is a v2/optional addition — do not build it yet unless explicitly requested.
- [ ] Confirm which platform(s) first: Windows only for v1, or also macOS/Linux? (Assume Windows-first unless told otherwise; revisit scope before starting macOS/Linux builds.)

### 2.2 PyInstaller build
- [ ] `pip install pyinstaller` in a clean build venv that has RIP + all base dependencies installed (same set as `pip install rip`, local-mode deps included; server-mode deps excluded unless bundling a "full" variant).
- [ ] Create `rip.spec` (or use `--onefile` flags directly) covering:
  - Entry point: `rip/cli.py` (`app`)
  - `--onefile` for a single distributable exe
  - `--collect-all` for packages known to hide resources via non-standard imports: `sentence_transformers`, `transformers`, `tree_sitter_language_pack`, `onnxruntime`
  - Explicitly bundle the ONNX model file(s) and tree-sitter language grammars as `--add-data` entries
  - `--name rip` (or `repo` to match the CLI command name)
- [ ] Build: `pyinstaller rip.spec` (or the equivalent one-line command).
- [ ] **Test on a genuinely clean Windows VM** (no Python installed) — this is the real test; building successfully on a dev machine with Python already present hides missing-dependency bugs.
- [ ] Verify:
  - `rip.exe --help` runs in <1s
  - `repo init`, `repo index`, `repo search` work fully offline
  - No missing-module runtime errors (PyInstaller frequently misses dynamic imports in ML libs — check `transformers`/`sentence-transformers` particularly closely)
- [ ] Record final exe size and confirm it's in the expected ~500–600MB range (CPU torch). If it balloons past ~700MB, investigate accidentally-bundled CUDA wheels.

### 2.3 Antivirus / SmartScreen mitigation
- [ ] Code-sign the exe with an Authenticode certificate (EV cert strongly preferred — builds SmartScreen reputation far faster than a standard cert).
- [ ] Submit the built exe to Microsoft for SmartScreen/Defender analysis in advance of public release (via the Windows Defender Security Intelligence submission portal) to reduce false-positive risk.
- [ ] If false positives persist, evaluate Nuitka as an alternative build backend (compiles to real machine code, generally lower AV flag rate than PyInstaller's bootloader).

### 2.4 Distribution
- [ ] Host the built exe (GitHub Releases is simplest and free for public repos; Netlify works too but isn't built for large binary hosting).
- [ ] File naming: `rip-windows-x64.exe` (add `-vX.Y.Z` version suffix).
- [ ] On the download page, disclose size upfront: *"~550MB — includes local ML models for fully offline semantic search."*
- [ ] Add a SHA256 checksum file alongside the release for integrity verification.

### 2.5 Optional v2 additions (do not build until v1 is validated)
- [ ] Inno Setup wrapper for PATH + Start Menu shortcuts + uninstaller, if user demand appears.
- [ ] macOS `.app` bundle + notarization.
- [ ] Linux `.AppImage`.
- [ ] Auto-update check on startup.

---

## 3. Explicitly Out of Scope for This Plan
- Thin bootstrap installer with first-run dependency download (rejected — see Section 0).
- Flag-file-based one-time setup flow.
- Self-managed venv creation inside an install directory.
- Silent/unattended install flags, CI/CD deployment installers.
- Website OS auto-detection and hosting integration (revisit only once both channels are shipping reliably).

---

## 4. Testing Checklist (both channels)

### pip channel
- [ ] Fresh venv, clean machine/container, `pip install rip` → `repo --help` works
- [ ] `pip install rip[server]` pulls server deps correctly
- [ ] Offline: `repo index`, `repo search`, `repo trace`, `repo impact` work without network after install
- [ ] `.repo-intel/local/` data written correctly (sqlite, graph.json, vectors.json)

### exe channel
- [ ] Clean Windows VM (no Python) — exe runs standalone
- [ ] `repo --help` <1s startup
- [ ] Full offline command set works (same list as above)
- [ ] Antivirus scan (Defender + at least one third-party AV) does not flag the exe
- [ ] Exe size confirmed in expected range

---

## 5. Immediate Next Steps (in order)
1. Finalize `pyproject.toml` dependency split (base vs. `[server]` extra) — **do this first**, since it affects both channels.
2. Configure CPU-only torch source.
3. Build + test wheel locally, publish to Test PyPI, validate, then publish to real PyPI.
4. Build PyInstaller exe from the same dependency set, test on a clean VM.
5. Address any AV flags before public release.
6. Publish both: PyPI package + GitHub Release with the exe.
