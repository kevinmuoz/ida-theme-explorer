from __future__ import annotations

import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SOURCES_FILE = ROOT / "data" / "sources.json"
OUTPUT_FILE = ROOT / "registry.json"

# HashMap GitHub repo to local cloned path
LOCAL_REPOS = {
    "can1357/IdaThemer": ROOT / "third_party" / "IdaThemer",
}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def slugify(text: str) -> str:
    text = text.strip().lower()
    text = text.replace("&", "and")
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text.strip("-")


def normalize_entry(entry: dict) -> dict:
    name = entry["name"].strip()
    return {
        "id": entry.get("id") or slugify(name),
        "name": name,
        "author": entry["author"].strip(),
        "repo": entry["repo"].strip(),
        "branch": entry.get("branch", "main").strip(),
        "theme_path": entry.get("theme_path", "").strip(),
        "description": entry.get("description", "").strip(),
        "preview": entry.get("preview", "").strip(),
    }


def build_single(source: dict) -> dict:
    return normalize_entry(source)


def build_folder(source: dict) -> list[dict]:
    repo = source["repo"]
    author = source["author"]
    branch = source.get("branch", "main")
    base_path = source["base_path"]
    exclude = set(source.get("exclude", []))

    local_repo = LOCAL_REPOS.get(repo)
    if not local_repo:
        raise RuntimeError(f"No local path configured for repo: {repo}")

    themes_root = local_repo / base_path
    if not themes_root.is_dir():
        raise RuntimeError(f"Missing directory: {themes_root}")

    out: list[dict] = []

    for child in sorted(themes_root.iterdir(), key=lambda p: p.name.lower()):
        if not child.is_dir():
            continue
        if child.name in exclude:
            continue
        if not (child / "theme.css").is_file():
            continue

        name = child.name.strip()
        entry = {
            "id": slugify(name),
            "name": name,
            "author": author,
            "repo": repo,
            "branch": branch,
            "theme_path": f"{base_path}/{child.name}",
            "description": f"{name} theme",
            "preview": "",
        }
        out.append(normalize_entry(entry))

    return out


def main() -> int:
    src = load_json(SOURCES_FILE)

    themes: list[dict] = []
    seen_ids: set[str] = set()

    for source in src.get("sources", []):
        typ = source["type"]

        if typ == "single":
            entries = [build_single(source)]
        elif typ == "folder":
            entries = build_folder(source)
        else:
            raise ValueError(f"Unknown source type: {typ}")

        for entry in entries:
            if entry["id"] in seen_ids:
                print(f"[skip] duplicate id: {entry['id']}")
                continue
            themes.append(entry)
            seen_ids.add(entry["id"])

    themes.sort(key=lambda t: t["name"].lower())

    out = {
        "version": src.get("version", 2),
        "themes": themes,
    }

    OUTPUT_FILE.write_text(
        json.dumps(out, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print(f"[ok] wrote {OUTPUT_FILE}")
    print(f"[ok] total themes: {len(themes)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())