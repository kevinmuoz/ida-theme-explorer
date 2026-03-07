from __future__ import annotations

import json
import os
import shutil
import zipfile
from io import BytesIO
from typing import Dict, List, Optional, Tuple
from urllib.request import urlopen, Request

import ida_diskio

REGISTRY_URL = (
    "https://raw.githubusercontent.com/"
    "kevinmuoz/ida-theme-explorer/main/registry.json"
)
USER_AGENT = "IDA-ThemeExplorer/1.0"
TIMEOUT = 45
_EXTS = {".css", ".png", ".svg", ".jpg", ".ico"}

def _user_dir() -> str:
    return ida_diskio.get_user_idadir()

def themes_dir() -> str:
    return os.path.join(_user_dir(), "themes")

def _manifest() -> str:
    return os.path.join(_user_dir(), "theme_explorer_installed.json")

def _cache_dir() -> str:
    d = os.path.join(_user_dir(), "theme_explorer_cache")
    os.makedirs(d, exist_ok=True)
    return d


def load_installed() -> Dict[str, dict]:
    if not os.path.isfile(_manifest()):
        return {}
    try:
        with open(_manifest(), "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _save_installed(data: Dict[str, dict]) -> None:
    os.makedirs(os.path.dirname(_manifest()), exist_ok=True)
    with open(_manifest(), "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


# registry
def fetch_registry(url: Optional[str] = None) -> List[dict]:
    req = Request(url or REGISTRY_URL, headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=TIMEOUT) as r:
        return json.loads(r.read().decode()).get("themes", [])

def fetch_registry_bundled() -> List[dict]:
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "registry.json")
    if not os.path.isfile(p):
        return []
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f).get("themes", [])


# preview
def get_preview_path(theme: dict) -> Optional[str]:
    tid = theme.get("id", "")
    if not tid:
        return None
    here = os.path.dirname(os.path.abspath(__file__))
    for ext in (".png", ".jpg"):
        for base in (os.path.join(here, "images"), _cache_dir()):
            p = os.path.join(base, f"{tid}{ext}")
            if os.path.isfile(p):
                return p
    return None

def download_preview(theme: dict) -> Optional[str]:
    url = theme.get("preview", "")
    tid = theme.get("id", "")
    if not url or not tid:
        return None
    try:
        req = Request(url, headers={"User-Agent": USER_AGENT})
        with urlopen(req, timeout=TIMEOUT) as r:
            data = r.read()
    except Exception:
        return None
    ext = ".jpg" if url.lower().endswith((".jpg", ".jpeg")) else ".png"
    dest = os.path.join(_cache_dir(), f"{tid}{ext}")
    with open(dest, "wb") as f:
        f.write(data)
    return dest


# extract 
def _download_zip(repo: str, branch: str) -> bytes:
    url = f"https://github.com/{repo}/archive/refs/heads/{branch}.zip"
    req = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=TIMEOUT) as r:
        return r.read()


def _extract(zip_bytes: bytes, dest: str, theme_path: str) -> None:
    """Extract theme assets from zip into dest.

    theme_path is the path INSIDE the repo (not inside the zip) where
    theme.css lives. "" means repo root. The GitHub zip always has a
    top-levevl folder like "repo-branch/", we prepend that automatically.
    """
    os.makedirs(dest, exist_ok=True)
    buf = BytesIO(zip_bytes)
    with zipfile.ZipFile(buf) as zf:
        members = zf.namelist()
        # GitHub top-level dir
        zip_root = members[0] if members else ""

        # build the prefix to match
        if theme_path:
            prefix = zip_root + theme_path.strip("/") + "/"
        else:
            prefix = zip_root

        for m in members:
            if m.endswith("/") or not m.startswith(prefix):
                continue
            rel = m[len(prefix):]
            if not rel:
                continue
            ext = os.path.splitext(rel)[1].lower()
            if ext not in _EXTS:
                continue
            out = os.path.join(dest, rel)
            os.makedirs(os.path.dirname(out), exist_ok=True)
            with zf.open(m) as src, open(out, "wb") as dst:
                dst.write(src.read())


def install_theme(theme: dict) -> Tuple[bool, str]:
    repo = theme.get("repo", "")
    branch = theme.get("branch", "main")
    tid = theme.get("id", "")
    name = theme.get("name", tid)
    theme_path = theme.get("theme_path", "")

    if not repo or not tid:
        return False, "Invalid theme (missing repo or id)."

    try:
        data = _download_zip(repo, branch)
    except Exception as e:
        return False, f"Download failed: {e}"

    dest = os.path.join(themes_dir(), tid)
    try:
        if os.path.exists(dest):
            shutil.rmtree(dest)
        _extract(data, dest, theme_path)
    except Exception as e:
        return False, f"Extraction failed: {e}"

    css = os.path.join(dest, "theme.css")
    if not os.path.isfile(css):
        files = []
        for r, _, fns in os.walk(dest):
            for fn in fns:
                files.append(os.path.relpath(os.path.join(r, fn), dest))
        return False, (
            f"theme.css not found.\n"
            f"Files: {', '.join(files[:15])}\n"
            f"Path: {dest}"
        )

    installed = load_installed()
    installed[tid] = {"name": name, "repo": repo, "branch": branch}
    _save_installed(installed)
    return True, (
        f"'{name}' installed.\n"
        f"Go to Options > Colors and select '{tid}' as current theme."
    )

def uninstall_theme(tid: str) -> Tuple[bool, str]:
    installed = load_installed()
    if tid not in installed:
        return False, "Not installed."
    dest = os.path.join(themes_dir(), tid)
    if os.path.exists(dest):
        try:
            shutil.rmtree(dest)
        except Exception as e:
            return False, f"Remove failed: {e}"
    name = installed[tid].get("name", tid)
    del installed[tid]
    _save_installed(installed)
    return True, f"'{name}' removed."