from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from .errors import ConfigError

POINTER_PATH = Path.home() / ".config" / "artefact-sync" / "config.json"
ARTEFACTS_DIRNAME = "artefacts"
PUSH_MODES = ("direct", "branch")
DEFAULT_FAVICON = "<link rel=\"icon\" href=\"data:,\">"


@dataclass(frozen=True)
class Pointer:
    repo: Path
    source: Path
    push: str


@dataclass(frozen=True)
class Site:
    base_url: str
    favicon: str
    catalogue_mode: str
    catalogue_page: PurePosixPath | None


@dataclass(frozen=True)
class Context:
    repo_root: Path
    source_root: Path
    artefacts_root: Path
    site: Site
    push: str = "direct"


def load_pointer(path: Path = POINTER_PATH) -> Pointer:
    if not path.is_file():
        raise ConfigError(f"no pointer at {path}; run 'artefact-sync init' first")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ConfigError(f"unreadable pointer at {path}: {error}") from error
    if not isinstance(raw, dict):
        raise ConfigError(f"pointer at {path} must be a JSON object")
    for key in ("repo", "source"):
        if not isinstance(raw.get(key), str) or not raw[key]:
            raise ConfigError(f"pointer at {path} needs a non-empty '{key}'")
    push = raw.get("push", "direct")
    if push not in PUSH_MODES:
        raise ConfigError(f"pointer 'push' must be one of {PUSH_MODES}, got {push!r}")
    return Pointer(Path(raw["repo"]).expanduser(), Path(raw["source"]).expanduser(), push)


def save_pointer(pointer: Pointer, path: Path = POINTER_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = {"repo": str(pointer.repo), "source": str(pointer.source), "push": pointer.push}
    path.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")


def site_from_dict(raw: dict) -> Site:
    if not isinstance(raw, dict):
        raise ConfigError("site must be an object")
    base_url = raw.get("base_url")
    if not isinstance(base_url, str) or not base_url.endswith("/"):
        raise ConfigError("site.base_url must be a URL ending in '/'")
    catalogue = raw.get("catalogue") or {"mode": "standalone"}
    if not isinstance(catalogue, dict):
        raise ConfigError("site.catalogue must be an object")
    mode = catalogue.get("mode", "standalone")
    if mode not in ("standalone", "inject"):
        raise ConfigError(f"site.catalogue.mode must be standalone or inject, got {mode!r}")
    page = catalogue.get("page")
    if mode == "inject" and not page:
        raise ConfigError("site.catalogue.mode 'inject' needs a 'page'")
    if page:
        if not isinstance(page, str) or "\\" in page:
            raise ConfigError("site.catalogue.page must be a safe relative path")
        page_path = PurePosixPath(page)
        if page_path.is_absolute() or any(part in {"", ".", ".."} for part in page_path.parts):
            raise ConfigError("site.catalogue.page must be a safe relative path")
    else:
        page_path = None
    return Site(
        base_url=base_url,
        favicon=raw.get("favicon", DEFAULT_FAVICON),
        catalogue_mode=mode,
        catalogue_page=page_path,
    )


def site_to_dict(site: Site) -> dict:
    catalogue: dict = {"mode": site.catalogue_mode}
    if site.catalogue_page is not None:
        catalogue["page"] = site.catalogue_page.as_posix()
    return {"base_url": site.base_url, "favicon": site.favicon, "catalogue": catalogue}


def build_context(pointer: Pointer, site: Site) -> Context:
    repo_root = pointer.repo.expanduser().resolve()
    return Context(
        repo_root=repo_root,
        source_root=pointer.source.expanduser().resolve(),
        artefacts_root=repo_root / ARTEFACTS_DIRNAME,
        site=site,
        push=pointer.push,
    )
