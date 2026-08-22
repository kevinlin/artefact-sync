# artefact-sync M1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the portable core of `artefact-sync` (`init`, `plan`, `sync`, `validate`), working
against a local repo with no network access.

**Architecture:** A stdlib-only Python package inside the skill directory. `cli.py` resolves
`(repo_root, source_root, site)` once into a frozen `Context` before dispatch; every core function
takes it as an argument so nothing below the CLI reads `~`, `cwd` or `__file__`. Dependency
direction is one-way (`cli` → `plan` → `render`/`catalogue`/`scan` → `manifest` → `errors`), which
keeps the core testable with no git, no network and no repo on disk.

**Tech Stack:** Python 3.9, standard library only, `unittest`.

**Spec:** [design_artefact-sync.md](design_artefact-sync.md). Its supporting evidence, with
`file:line` citations into the prior art, is [extraction-analysis.md](../research/extraction-analysis.md).

## Global Constraints

Every task's requirements implicitly include this section.

- **Python 3.9.** The tool must run under stock macOS `/usr/bin/python3` (3.9.6). Every module
  starts with `from __future__ import annotations` so `X | None` annotations parse on 3.9.
- **Standard library only.** No third-party import in the shipped package or in its tests, ever.
- **Test command:** `python3 -m unittest discover -s tests -t . -v`. Never pytest.
- **British spelling** in every user-facing string, path and identifier: `artefacts`, `catalogue`.
  57 published URLs already use it.
- **No emoji** in any output.
- **Repo root is the skill directory.** This repo is cloned to `~/.claude/skills/artefact-sync/`.
  `SKILL.md` sits at the root next to the `artefact_sync/` package.
- **Prior art, read-only:** `/Users/keli/dev/github-kevinlin/kevinlin.github.io/scripts/artefacts.py`
  and `tests/test_artefacts.py`. When a task says "port from `artefacts.py:X-Y`", open those exact
  lines and carry the behaviour across. Do not invent behaviour a citation does not support.
- **Never write to `/Users/keli/dev/github-kevinlin/kevinlin.github.io`.** It is a live site with 57
  published URLs. Read it; do not touch it. `git -C <that repo> status --short` must stay empty.
- **Exit codes:** `0` success, `1` error, `3` blocked and needs a human decision.

---

## File Structure

```
artefact-sync/                    repo root == skill directory
  SKILL.md                        how the model drives the tool
  artefact_sync/
    __init__.py
    errors.py                     exception types shared across modules
    config.py                     pointer file + site block -> Context
    manifest.py                   models, decode, validate, normalise, HEAD invariants
    scan.py                       source walk, ignore rules, allowlist, SVG validation
    render.py                     markdown page rendering, HTML transformation
    catalogue.py                  standalone shell generation, marker injection
    propose.py                    slug/title/collection derivation, rename detection
    plan.py                       diffing, consequence grouping, plan formatting
    apply.py                      atomic writes, deletions, verification
    cli.py                        parser, Context resolution, dispatch, exit codes
    assets/
      page-template.html          neutral $-placeholder artefact page
      catalogue-template.html     neutral standalone catalogue shell
      marked.min.js               vendored renderer, copied into repos by init
  tests/
    __init__.py
    helpers.py                    fixture source tree and destination repo builders
    test_stdlib_only.py           guard: no third-party imports
    test_config.py  test_manifest.py  test_scan.py  test_render.py
    test_catalogue.py  test_propose.py  test_plan.py  test_apply.py
    test_cli.py  test_init.py  test_m1_end_to_end.py
```

`errors.py` exists so `manifest.py` and `scan.py` can raise the same exception types without
importing each other. `models` are not a separate file: `Collection`/`Entry`/`Manifest` live in
`manifest.py`, `Site`/`Context` in `config.py`, `Change`/`Note`/`SyncPlan` in `plan.py` — each beside
the code that owns it, with no cycles.

`publish.py`, `provider.py` and `selfcheck.py` are M2. They are named here only so nobody adds them
early.

---

### Task 1: Skeleton, test harness, and the stdlib-only guard

**Files:**
- Create: `artefact_sync/__init__.py`, `artefact_sync/errors.py`, `tests/__init__.py`,
  `tests/helpers.py`
- Test: `tests/test_stdlib_only.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `ArtefactSyncError`, `ConfigError(ArtefactSyncError)`,
  `ValidationError(ArtefactSyncError)`, `TransformationError(ArtefactSyncError)`,
  `UnlistedSources(ArtefactSyncError)` with attribute `sources: tuple[PurePosixPath, ...]`.
  `tests.helpers.make_source_tree(tmp, files: dict[str, bytes]) -> Path` and
  `tests.helpers.make_repo(tmp, files: dict[str, bytes]) -> Path`, which returns a real
  `git init`-ed repo with one commit.

- [x] **Step 1: Write the failing test**

```python
# tests/test_stdlib_only.py
from __future__ import annotations

import ast
import pathlib
import unittest

PACKAGE = pathlib.Path(__file__).resolve().parent.parent / "artefact_sync"

# sys.stdlib_module_names is 3.10+, and the floor is 3.9, so the allowlist is explicit.
ALLOWED = {
    "__future__", "argparse", "collections", "contextlib", "dataclasses", "datetime",
    "difflib", "fnmatch", "hashlib", "html", "http", "io", "json", "os", "pathlib",
    "re", "shutil", "string", "subprocess", "sys", "tempfile", "textwrap", "time",
    "typing", "urllib", "artefact_sync",
}


class StdlibOnlyTests(unittest.TestCase):
    def test_every_module_imports_only_stdlib(self) -> None:
        offenders = []
        for path in sorted(PACKAGE.rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    names = [a.name.split(".")[0] for a in node.names]
                elif isinstance(node, ast.ImportFrom):
                    names = [(node.module or "").split(".")[0]] if node.level == 0 else []
                else:
                    continue
                offenders += [
                    f"{path.name}:{node.lineno} {n}" for n in names if n and n not in ALLOWED
                ]
        self.assertEqual([], offenders)

    def test_every_module_has_future_annotations(self) -> None:
        missing = [
            path.name
            for path in sorted(PACKAGE.rglob("*.py"))
            if path.name != "__init__.py"
            and "from __future__ import annotations" not in path.read_text(encoding="utf-8")
        ]
        self.assertEqual([], missing)
```

- [x] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest discover -s tests -t . -v`
Expected: FAIL — `artefact_sync` package does not exist yet.

- [x] **Step 3: Write minimal implementation**

```python
# artefact_sync/__init__.py
"""Portable one-way sync from a local folder to an artefacts/ tree in a Pages repo."""
```

```python
# artefact_sync/errors.py
from __future__ import annotations

from pathlib import PurePosixPath


class ArtefactSyncError(Exception):
    """Anything this tool raises on purpose."""


class ConfigError(ArtefactSyncError):
    """The pointer file or the manifest's site block is missing or malformed."""


class ValidationError(ArtefactSyncError):
    """A manifest, a source file, or a destination tree failed a check."""


class TransformationError(ArtefactSyncError):
    """A source file could not be turned into its published bytes."""


class UnlistedSources(ArtefactSyncError):
    """Approved source files with no manifest entry. Stops the run and asks."""

    def __init__(self, sources: tuple[PurePosixPath, ...]) -> None:
        super().__init__(f"{len(sources)} approved source(s) have no manifest entry")
        self.sources = sources
```

```python
# tests/helpers.py
from __future__ import annotations

import subprocess
from pathlib import Path


def _write(root: Path, files: dict[str, bytes]) -> Path:
    for relative, data in files.items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    return root


def make_source_tree(tmp: Path, files: dict[str, bytes]) -> Path:
    """A source folder. Keys are paths relative to the source root."""
    root = tmp / "source"
    root.mkdir(parents=True, exist_ok=True)
    return _write(root, files)


def make_repo(tmp: Path, files: dict[str, bytes]) -> Path:
    """A real git repo with one commit, so HEAD-diffing tests have a HEAD."""
    root = tmp / "repo"
    root.mkdir(parents=True, exist_ok=True)
    _write(root, files or {"README.md": b"repo\n"})
    env = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
           "GIT_COMMITTER_EMAIL": "t@t", "PATH": "/usr/bin:/bin:/usr/local/bin"}
    for args in (["init", "-q", "-b", "main"], ["add", "-A"], ["commit", "-q", "-m", "seed"]):
        subprocess.run(["git", *args], cwd=root, env=env, check=True)
    return root
```

Create empty `tests/__init__.py`.

- [x] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest discover -s tests -t . -v`
Expected: PASS, 2 tests.

- [x] **Step 5: Commit**

```bash
git add artefact_sync tests
git commit -m "feat: package skeleton, error types, stdlib-only guard"
```

---

### Task 2: `config.py` — pointer file, site block, Context

**Files:**
- Create: `artefact_sync/config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Consumes: `errors.ConfigError`.
- Produces:
  - `POINTER_PATH: Path` (default `~/.config/artefact-sync/config.json`)
  - `Pointer(repo: Path, source: Path, push: str)` frozen dataclass, `push` in `{"direct","branch"}`
  - `Site(base_url: str, favicon: str, catalogue_mode: str, catalogue_page: PurePosixPath | None)`
  - `Context(repo_root: Path, source_root: Path, artefacts_root: Path, site: Site)`
  - `load_pointer(path: Path = POINTER_PATH) -> Pointer`
  - `save_pointer(pointer: Pointer, path: Path = POINTER_PATH) -> None`
  - `site_from_dict(raw: dict) -> Site`, `site_to_dict(site: Site) -> dict`
  - `build_context(pointer: Pointer, site: Site) -> Context`

Wholly new code — the prior art derives its defaults from the script's own parent directory
(`artefacts.py:2250-2269`), which after extraction points at the skill directory.

- [x] **Step 1: Write the failing test**

```python
# tests/test_config.py
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path, PurePosixPath

from artefact_sync import config
from artefact_sync.errors import ConfigError


class PointerTests(unittest.TestCase):
    def test_round_trips_through_the_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "nested" / "config.json"
            pointer = config.Pointer(Path("/r"), Path("/s"), "direct")
            config.save_pointer(pointer, target)
            self.assertEqual(pointer, config.load_pointer(target))

    def test_missing_pointer_names_the_command_that_creates_it(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ConfigError) as caught:
                config.load_pointer(Path(tmp) / "absent.json")
        self.assertIn("init", str(caught.exception))

    def test_rejects_an_unknown_push_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "config.json"
            target.write_text(json.dumps({"repo": "/r", "source": "/s", "push": "yolo"}))
            with self.assertRaises(ConfigError):
                config.load_pointer(target)


class SiteTests(unittest.TestCase):
    def test_defaults_to_a_standalone_catalogue(self) -> None:
        site = config.site_from_dict({"base_url": "https://x.example/artefacts/"})
        self.assertEqual("standalone", site.catalogue_mode)
        self.assertIsNone(site.catalogue_page)

    def test_inject_mode_requires_a_page(self) -> None:
        with self.assertRaises(ConfigError):
            config.site_from_dict(
                {"base_url": "https://x.example/artefacts/", "catalogue": {"mode": "inject"}}
            )

    def test_base_url_must_end_with_a_slash(self) -> None:
        with self.assertRaises(ConfigError):
            config.site_from_dict({"base_url": "https://x.example/artefacts"})

    def test_site_survives_a_json_round_trip(self) -> None:
        site = config.site_from_dict(
            {
                "base_url": "https://x.example/artefacts/",
                "favicon": "<link rel='icon' href='data:,'>",
                "catalogue": {"mode": "inject", "page": "index.html"},
            }
        )
        self.assertEqual(site, config.site_from_dict(config.site_to_dict(site)))
        self.assertEqual(PurePosixPath("index.html"), site.catalogue_page)


class ContextTests(unittest.TestCase):
    def test_artefacts_root_hangs_off_the_repo_not_the_cwd(self) -> None:
        pointer = config.Pointer(Path("/r"), Path("/s"), "direct")
        site = config.site_from_dict({"base_url": "https://x.example/artefacts/"})
        context = config.build_context(pointer, site)
        self.assertEqual(Path("/r/artefacts"), context.artefacts_root)
```

- [x] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_config -v`
Expected: FAIL — `No module named 'artefact_sync.config'`.

- [x] **Step 3: Write minimal implementation**

```python
# artefact_sync/config.py
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


def load_pointer(path: Path = POINTER_PATH) -> Pointer:
    if not path.is_file():
        raise ConfigError(f"no pointer at {path}; run 'artefact-sync init' first")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ConfigError(f"unreadable pointer at {path}: {error}") from error
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
    base_url = raw.get("base_url")
    if not isinstance(base_url, str) or not base_url.endswith("/"):
        raise ConfigError("site.base_url must be a URL ending in '/'")
    catalogue = raw.get("catalogue") or {"mode": "standalone"}
    mode = catalogue.get("mode", "standalone")
    if mode not in ("standalone", "inject"):
        raise ConfigError(f"site.catalogue.mode must be standalone or inject, got {mode!r}")
    page = catalogue.get("page")
    if mode == "inject" and not page:
        raise ConfigError("site.catalogue.mode 'inject' needs a 'page'")
    return Site(
        base_url=base_url,
        favicon=raw.get("favicon", DEFAULT_FAVICON),
        catalogue_mode=mode,
        catalogue_page=PurePosixPath(page) if page else None,
    )


def site_to_dict(site: Site) -> dict:
    catalogue: dict = {"mode": site.catalogue_mode}
    if site.catalogue_page is not None:
        catalogue["page"] = site.catalogue_page.as_posix()
    return {"base_url": site.base_url, "favicon": site.favicon, "catalogue": catalogue}


def build_context(pointer: Pointer, site: Site) -> Context:
    repo_root = pointer.repo.expanduser()
    return Context(
        repo_root=repo_root,
        source_root=pointer.source.expanduser(),
        artefacts_root=repo_root / ARTEFACTS_DIRNAME,
        site=site,
    )
```

- [x] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_config -v`
Expected: PASS, 8 tests.

- [x] **Step 5: Commit**

```bash
git add artefact_sync/config.py tests/test_config.py
git commit -m "feat(config): pointer file, site block, Context resolution"
```

---

### Task 3: `manifest.py` — models, decode, validate, serialise

**Files:**
- Create: `artefact_sync/manifest.py`
- Test: `tests/test_manifest.py`

**Interfaces:**
- Consumes: `config.Site`, `config.site_from_dict`, `config.site_to_dict`, `errors.ValidationError`.
- Produces:
  - `Collection(id, title, description, section, section_order, order)`
  - `Entry(id, source: PurePosixPath, destination: PurePosixPath, title, collection, order,
    replacements: dict[str, str], description: str | None, date: str | None)`
  - `Manifest(version: int, site: Site, protected_files, ignored_sources, collections, entries)`
  - `manifest_from_dict(raw) -> Manifest`, `manifest_to_json(m) -> str`,
    `manifest_from_bytes(b) -> Manifest`, `validate_manifest(m) -> None`,
    `normalize_orders(m) -> Manifest`, `load_manifest(artefacts_root: Path) -> Manifest`
  - `APPROVED_EXTENSIONS`, `DIRECTORY_INDEX_EXTENSIONS`, `MANIFEST_NAME = "manifest.json"`,
    `TEMPLATE_NAME = "page-template.html"`, `CATALOGUE_NAME = "index.html"`

**Port note.** Carry `manifest_from_dict`, `validate_manifest`, `normalize_orders` and
`manifest_to_json` from `artefacts.py:215-446` and `artefacts.py:1394-1433`. Three deltas:
`APPROVED_EXTENSIONS` gains `.pdf .webp .gif .svg` (`artefacts.py:25-26` has only six); `Entry` gains
`description` and `date` (`artefacts.py:112-120` has neither, and `manifest_from_dict` drops unknown
keys, so today the worked example is silently stripped); `Manifest` gains `site`.

- [x] **Step 1: Write the failing test**

```python
# tests/test_manifest.py
from __future__ import annotations

import json
import unittest
from pathlib import PurePosixPath

from artefact_sync import manifest as m
from artefact_sync.errors import ValidationError

SITE = {"base_url": "https://x.example/artefacts/"}


def raw(**overrides) -> dict:
    body = {
        "version": 1,
        "site": SITE,
        "protected_files": ["vendor/marked.min.js"],
        "ignored_sources": [],
        "collections": [
            {"id": "c", "title": "C", "section": "S", "section_order": 10, "order": 10}
        ],
        "entries": [
            {
                "id": "e",
                "source": "a/b.png",
                "destination": "a/b.png",
                "title": "B",
                "collection": "c",
                "order": 10,
                "replacements": {},
            }
        ],
    }
    body.update(overrides)
    return body


class SchemaTests(unittest.TestCase):
    def test_loads_a_valid_manifest(self) -> None:
        parsed = m.manifest_from_dict(raw())
        self.assertEqual(1, parsed.version)
        self.assertEqual(PurePosixPath("a/b.png"), parsed.entries[0].destination)

    def test_rejects_an_unknown_version(self) -> None:
        with self.assertRaises(ValidationError):
            m.manifest_from_dict(raw(version=99))

    def test_rejects_duplicate_destinations(self) -> None:
        body = raw()
        second = dict(body["entries"][0], id="e2", source="a/c.png")
        body["entries"] = [body["entries"][0], second]
        with self.assertRaises(ValidationError):
            m.validate_manifest(m.manifest_from_dict(body))

    def test_rejects_a_parent_traversal_destination(self) -> None:
        body = raw()
        body["entries"][0]["destination"] = "../escape.png"
        with self.assertRaises(ValidationError):
            m.validate_manifest(m.manifest_from_dict(body))

    def test_rejects_an_entry_in_an_unknown_collection(self) -> None:
        body = raw()
        body["entries"][0]["collection"] = "nope"
        with self.assertRaises(ValidationError):
            m.validate_manifest(m.manifest_from_dict(body))


class NewFieldTests(unittest.TestCase):
    def test_description_and_date_survive_a_round_trip(self) -> None:
        body = raw()
        body["entries"][0]["description"] = "what it is"
        body["entries"][0]["date"] = "2026-03-28"
        once = m.manifest_from_dict(body)
        twice = m.manifest_from_bytes(m.manifest_to_json(once).encode("utf-8"))
        self.assertEqual("what it is", twice.entries[0].description)
        self.assertEqual("2026-03-28", twice.entries[0].date)

    def test_absent_description_and_date_stay_absent_in_json(self) -> None:
        emitted = json.loads(m.manifest_to_json(m.manifest_from_dict(raw())))
        self.assertNotIn("description", emitted["entries"][0])
        self.assertNotIn("date", emitted["entries"][0])

    def test_rejects_a_date_that_is_not_iso(self) -> None:
        body = raw()
        body["entries"][0]["date"] = "28/03/2026"
        with self.assertRaises(ValidationError):
            m.manifest_from_dict(body)

    def test_site_block_survives_a_round_trip(self) -> None:
        once = m.manifest_from_dict(raw())
        twice = m.manifest_from_bytes(m.manifest_to_json(once).encode("utf-8"))
        self.assertEqual(once.site, twice.site)


class ExtensionTests(unittest.TestCase):
    def test_the_new_types_are_approved(self) -> None:
        for suffix in (".pdf", ".webp", ".gif", ".svg"):
            self.assertIn(suffix, m.APPROVED_EXTENSIONS)

    def test_html_destination_must_be_a_directory_index(self) -> None:
        body = raw()
        body["entries"][0]["source"] = "a/b.html"
        body["entries"][0]["destination"] = "a/b.html"
        with self.assertRaises(ValidationError):
            m.validate_manifest(m.manifest_from_dict(body))
```

- [x] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_manifest -v`
Expected: FAIL — `No module named 'artefact_sync.manifest'`.

- [x] **Step 3: Write minimal implementation**

Port `artefacts.py:100-446` and `artefacts.py:1394-1433` into `artefact_sync/manifest.py`, replacing
the module-level constants with the block below and threading `site` through
`manifest_from_dict`/`manifest_to_json`. `_resolve_within` (`artefacts.py:84-99`) comes across
unchanged — it is the path-containment guard every other module depends on.

```python
# artefact_sync/manifest.py — the deltas from the prior art
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date as date_cls
from pathlib import Path, PurePosixPath

from .config import Site, site_from_dict, site_to_dict
from .errors import ValidationError

MANIFEST_NAME = "manifest.json"
TEMPLATE_NAME = "page-template.html"
CATALOGUE_NAME = "index.html"
VENDOR_NAME = "marked.min.js"
SUPPORTED_VERSION = 1

DIRECTORY_INDEX_EXTENSIONS = frozenset({".html", ".md"})
APPROVED_EXTENSIONS = frozenset(
    {".html", ".md", ".png", ".jpeg", ".jpg", ".ico", ".pdf", ".webp", ".gif", ".svg"}
)
# Control files that live inside the published tree and are never orphans.
CONTROL_FILES = frozenset({MANIFEST_NAME, TEMPLATE_NAME, CATALOGUE_NAME})

ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@dataclass(frozen=True)
class Entry:
    id: str
    source: PurePosixPath
    destination: PurePosixPath
    title: str
    collection: str
    order: int
    replacements: dict[str, str] = field(default_factory=dict)
    description: str | None = None
    date: str | None = None


@dataclass(frozen=True)
class Manifest:
    version: int
    site: Site
    protected_files: tuple[PurePosixPath, ...]
    ignored_sources: tuple[str, ...]
    collections: tuple["Collection", ...]
    entries: tuple[Entry, ...]


def _entry_from_dict(raw: dict) -> Entry:
    stamp = raw.get("date")
    if stamp is not None:
        if not isinstance(stamp, str) or not ISO_DATE.match(stamp):
            raise ValidationError(f"entry {raw.get('id')!r}: date must be YYYY-MM-DD")
        try:
            date_cls.fromisoformat(stamp)
        except ValueError as error:
            raise ValidationError(f"entry {raw.get('id')!r}: {error}") from error
    return Entry(
        id=raw["id"],
        source=PurePosixPath(raw["source"]),
        destination=PurePosixPath(raw["destination"]),
        title=raw["title"],
        collection=raw["collection"],
        order=int(raw["order"]),
        replacements=dict(raw.get("replacements") or {}),
        description=raw.get("description"),
        date=stamp,
    )


def _entry_to_dict(entry: Entry) -> dict:
    body = {
        "id": entry.id,
        "source": entry.source.as_posix(),
        "destination": entry.destination.as_posix(),
        "title": entry.title,
        "collection": entry.collection,
        "order": entry.order,
        "replacements": dict(entry.replacements),
    }
    # Absent stays absent: emitting nulls would churn every manifest on first sync.
    if entry.description is not None:
        body["description"] = entry.description
    if entry.date is not None:
        body["date"] = entry.date
    return body


def load_manifest(artefacts_root: Path) -> Manifest:
    path = artefacts_root / MANIFEST_NAME
    if not path.is_file():
        raise ValidationError(f"no manifest at {path}; run 'artefact-sync init' first")
    return manifest_from_bytes(path.read_bytes())
```

`manifest_from_dict` calls `site_from_dict(raw["site"])`; `manifest_to_json` emits
`"site": site_to_dict(m.site)` as the second key, after `version`. Keep the prior art's key order for
everything else so a re-serialised manifest diffs cleanly.

- [x] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_manifest -v`
Expected: PASS, 11 tests.

- [x] **Step 5: Commit**

```bash
git add artefact_sync/manifest.py tests/test_manifest.py
git commit -m "feat(manifest): port schema, add site block, description and date"
```

---

### Task 4: `manifest.py` — the published-URL invariants

**Files:**
- Modify: `artefact_sync/manifest.py`
- Test: `tests/test_manifest_invariants.py`

**Interfaces:**
- Consumes: `tests.helpers.make_repo`, `Manifest`, `Entry`.
- Produces:
  - `head_manifest(repo_root: Path) -> Manifest | None` — reads
    `git show HEAD:artefacts/manifest.json`, returns `None` when the path is not in HEAD.
  - `check_published_invariants(current: Manifest, head: Manifest | None) -> None` — raises
    `ValidationError` naming the URL that would break.

This is the highest-risk task in M1: new enforcement, not ported behaviour. Nothing enforces either
invariant today. `validate_manifest` (`artefacts.py:335-392`) checks shape and uniqueness and never
compares against HEAD, and the planner (`artefacts.py:1538-1556`) silently treats a changed
`destination` as add-new plus delete-old.

- [x] **Step 1: Write the failing test**

```python
# tests/test_manifest_invariants.py
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path, PurePosixPath

from artefact_sync import manifest as m
from artefact_sync.errors import ValidationError
from tests.helpers import make_repo


def entry(**overrides) -> m.Entry:
    body = dict(
        id="e", source=PurePosixPath("a.png"), destination=PurePosixPath("a.png"),
        title="A", collection="c", order=10, replacements={},
    )
    body.update(overrides)
    return m.Entry(**body)


def manifest(entries) -> m.Manifest:
    from artefact_sync.config import site_from_dict

    return m.Manifest(
        version=1,
        site=site_from_dict({"base_url": "https://x.example/artefacts/"}),
        protected_files=(),
        ignored_sources=(),
        collections=(m.Collection(id="c", title="C", description=None, section="S",
                                  section_order=10, order=10),),
        entries=tuple(entries),
    )


class InvariantTests(unittest.TestCase):
    def test_a_changed_destination_is_rejected_and_names_the_url(self) -> None:
        head = manifest([entry()])
        current = manifest([entry(destination=PurePosixPath("moved.png"))])
        with self.assertRaises(ValidationError) as caught:
            m.check_published_invariants(current, head)
        self.assertIn("a.png", str(caught.exception))

    def test_a_changed_title_is_rejected(self) -> None:
        head = manifest([entry()])
        current = manifest([entry(title="Renamed")])
        with self.assertRaises(ValidationError):
            m.check_published_invariants(current, head)

    def test_a_changed_source_is_allowed_when_the_destination_holds(self) -> None:
        head = manifest([entry()])
        current = manifest([entry(source=PurePosixPath("renamed.png"))])
        m.check_published_invariants(current, head)  # must not raise

    def test_a_new_entry_is_allowed(self) -> None:
        head = manifest([entry()])
        current = manifest([entry(), entry(id="e2", source=PurePosixPath("b.png"),
                                          destination=PurePosixPath("b.png"))])
        m.check_published_invariants(current, head)

    def test_a_removed_entry_is_allowed(self) -> None:
        m.check_published_invariants(manifest([]), manifest([entry()]))

    def test_no_head_manifest_means_nothing_to_protect(self) -> None:
        m.check_published_invariants(manifest([entry()]), None)


class HeadManifestTests(unittest.TestCase):
    def test_returns_none_when_the_repo_has_no_manifest_in_head(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(Path(tmp), {"README.md": b"x\n"})
            self.assertIsNone(m.head_manifest(repo))
```

- [x] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_manifest_invariants -v`
Expected: FAIL — `module 'artefact_sync.manifest' has no attribute 'check_published_invariants'`.

- [x] **Step 3: Write minimal implementation**

```python
# append to artefact_sync/manifest.py
import subprocess


def head_manifest(repo_root: Path) -> Manifest | None:
    """The manifest as of HEAD, or None when it was never committed."""
    result = subprocess.run(
        ["git", "show", f"HEAD:artefacts/{MANIFEST_NAME}"],
        cwd=str(repo_root), capture_output=True,
    )
    if result.returncode != 0:
        return None
    return manifest_from_bytes(result.stdout)


def check_published_invariants(current: Manifest, head: Manifest | None) -> None:
    """A published entry keeps its URL and its title. Both are how a live link breaks.

    Only entries present in BOTH manifests are compared: adding and removing entries is
    ordinary work, and a changed `source` is a rename, which Task 11 handles by keeping
    the destination rather than deriving a new one.
    """
    if head is None:
        return
    published = {entry.id: entry for entry in head.entries}
    problems = []
    for entry in current.entries:
        was = published.get(entry.id)
        if was is None:
            continue
        if entry.destination != was.destination:
            problems.append(
                f"entry {entry.id!r}: destination {was.destination.as_posix()} -> "
                f"{entry.destination.as_posix()} would break the published URL "
                f"for {was.destination.as_posix()}"
            )
        if entry.title != was.title:
            problems.append(
                f"entry {entry.id!r}: title {was.title!r} -> {entry.title!r}; "
                "an existing entry is never re-titled"
            )
    if problems:
        raise ValidationError("\n".join(problems))
```

- [x] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_manifest_invariants -v`
Expected: PASS, 7 tests.

- [x] **Step 5: Commit**

```bash
git add artefact_sync/manifest.py tests/test_manifest_invariants.py
git commit -m "feat(manifest): enforce frozen destination and stable title against HEAD"
```

---

### Task 5: `scan.py` — walk, allowlist, glob ignores

**Files:**
- Create: `artefact_sync/scan.py`
- Test: `tests/test_scan.py`

**Interfaces:**
- Consumes: `manifest.APPROVED_EXTENSIONS`, `errors.ValidationError`.
- Produces:
  - `SourceInventory(approved: tuple[PurePosixPath, ...], excluded: tuple[tuple[str, int], ...])`
  - `scan_source(source_root: Path, repo_root: Path) -> SourceInventory`
  - `is_ignored(source: PurePosixPath, rules: tuple[str, ...]) -> bool`
  - `apply_source_ignores(inventory, rules) -> tuple[SourceInventory, tuple[tuple[str, int], ...]]`

**Port note.** From `artefacts.py:447-524`. Two deltas. First, the literal `kevinlin.github.io`
directory prune (`artefacts.py:454-464`) is deleted and replaced by pruning the *resolved destination
repo* when it happens to sit under the source root — a public user's folder may legitimately be named
anything. Second, `is_ignored` (`artefacts.py:488-493`) is exact-match or literal `dir/` prefix only;
it gains `fnmatch`, without which the seeded `*.local.*` rule matches nothing and publishes the files
it was meant to hide.

- [x] **Step 1: Write the failing test**

```python
# tests/test_scan.py
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path, PurePosixPath

from artefact_sync import scan
from tests.helpers import make_repo, make_source_tree


class WalkTests(unittest.TestCase):
    def test_reports_only_approved_extensions_and_counts_the_rest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = make_source_tree(Path(tmp), {
                "a/keep.png": b"1", "a/keep.svg": b"<svg/>", "a/skip.psd": b"2",
                "a/skip2.psd": b"3", "a/.DS_Store": b"4",
            })
            inventory = scan.scan_source(source, Path(tmp) / "nowhere")
        self.assertEqual(
            [PurePosixPath("a/keep.png"), PurePosixPath("a/keep.svg")],
            sorted(inventory.approved),
        )
        self.assertIn((".psd", 2), inventory.excluded)

    def test_prunes_the_destination_repo_when_it_sits_inside_the_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = make_source_tree(Path(tmp), {"a/keep.png": b"1"})
            repo = make_repo(source, {"artefacts/published.png": b"2"})
            inventory = scan.scan_source(source, repo)
        self.assertEqual([PurePosixPath("a/keep.png")], sorted(inventory.approved))

    def test_rejects_symlinks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = make_source_tree(Path(tmp), {"real.png": b"1"})
            (source / "link.png").symlink_to(source / "real.png")
            inventory = scan.scan_source(source, Path(tmp) / "nowhere")
        self.assertEqual([PurePosixPath("real.png")], sorted(inventory.approved))


class IgnoreTests(unittest.TestCase):
    def test_a_directory_rule_ignores_the_whole_subtree(self) -> None:
        self.assertTrue(scan.is_ignored(PurePosixPath("talk/prompts/x.md"), ("talk/prompts/",)))

    def test_a_directory_rule_does_not_match_a_sibling_prefix(self) -> None:
        self.assertFalse(scan.is_ignored(PurePosixPath("talk/promptsy.md"), ("talk/prompts/",)))

    def test_an_exact_rule_matches_only_that_file(self) -> None:
        self.assertTrue(scan.is_ignored(PurePosixPath("a/b.md"), ("a/b.md",)))
        self.assertFalse(scan.is_ignored(PurePosixPath("a/bb.md"), ("a/b.md",)))

    def test_a_glob_rule_matches_at_any_depth(self) -> None:
        self.assertTrue(scan.is_ignored(PurePosixPath("deep/a.local.html"), ("*.local.*",)))
        self.assertTrue(scan.is_ignored(PurePosixPath("a.local.html"), ("*.local.*",)))

    def test_the_dotfile_seed_matches_hidden_files_at_any_depth(self) -> None:
        self.assertTrue(scan.is_ignored(PurePosixPath("deep/.env"), (".*",)))
        self.assertFalse(scan.is_ignored(PurePosixPath("deep/env"), (".*",)))

    def test_rule_counts_are_reported_so_a_dead_rule_is_visible(self) -> None:
        inventory = scan.SourceInventory(
            approved=(PurePosixPath("a.local.html"), PurePosixPath("b.png")), excluded=()
        )
        kept, counts = scan.apply_source_ignores(inventory, ("*.local.*", "never-matches/"))
        self.assertEqual((PurePosixPath("b.png"),), kept.approved)
        self.assertIn(("never-matches/", 0), counts)
```

- [x] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_scan -v`
Expected: FAIL — `No module named 'artefact_sync.scan'`.

- [x] **Step 3: Write minimal implementation**

```python
# artefact_sync/scan.py
from __future__ import annotations

import fnmatch
import os
from dataclasses import dataclass, replace
from pathlib import Path, PurePosixPath

from .manifest import APPROVED_EXTENSIONS

IGNORED_METADATA_NAMES = frozenset({".DS_Store", "Thumbs.db"})


@dataclass(frozen=True)
class SourceInventory:
    approved: tuple[PurePosixPath, ...]
    excluded: tuple[tuple[str, int], ...]


def scan_source(source_root: Path, repo_root: Path) -> SourceInventory:
    """Every approved file under the source root, plus a count of what was skipped.

    Symlinks are refused rather than followed: a link out of the source root would
    publish a file the user never put there. The destination repo is pruned when it
    happens to live inside the source root, replacing the prior art's hardcoded
    `kevinlin.github.io` directory-name guard.
    """
    approved: list[PurePosixPath] = []
    skipped: dict[str, int] = {}
    try:
        pruned = repo_root.resolve()
    except OSError:
        pruned = repo_root
    root = source_root.resolve()

    for dirpath, dirnames, filenames in os.walk(root):
        here = Path(dirpath)
        dirnames[:] = sorted(
            name
            for name in dirnames
            if not (here / name).is_symlink() and (here / name).resolve() != pruned
        )
        for name in sorted(filenames):
            path = here / name
            if path.is_symlink() or name in IGNORED_METADATA_NAMES:
                continue
            relative = PurePosixPath(path.relative_to(root).as_posix())
            suffix = path.suffix.lower()
            if suffix in APPROVED_EXTENSIONS:
                approved.append(relative)
            else:
                skipped[suffix or "(no suffix)"] = skipped.get(suffix or "(no suffix)", 0) + 1
    return SourceInventory(
        approved=tuple(approved),
        excluded=tuple(sorted(skipped.items())),
    )


def is_ignored(source: PurePosixPath, rules: tuple[str, ...]) -> bool:
    """Three rule shapes: `dir/` prefix, glob, exact path.

    The glob arm is what makes the seeded `*.local.*` and `.*` rules work. It is tried
    against both the full relative path and the bare filename, so a rule needs no `**/`
    prefix to reach a nested file.
    """
    text = source.as_posix()
    for rule in rules:
        if rule.endswith("/"):
            if text.startswith(rule):
                return True
        elif any(char in rule for char in "*?["):
            if fnmatch.fnmatchcase(text, rule) or fnmatch.fnmatchcase(source.name, rule):
                return True
        elif text == rule:
            return True
    return False


def apply_source_ignores(
    inventory: SourceInventory, rules: tuple[str, ...]
) -> tuple[SourceInventory, tuple[tuple[str, int], ...]]:
    """The inventory without ignored sources, plus each rule's match count.

    Counts are returned rather than logged because a silently skipped file is the one
    way this list can lose work, and a rule matching nothing is usually a typo.
    """
    kept = tuple(s for s in inventory.approved if not is_ignored(s, rules))
    counts = tuple(
        (rule, sum(1 for s in inventory.approved if is_ignored(s, (rule,)))) for rule in rules
    )
    return replace(inventory, approved=kept), counts
```

- [x] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_scan -v`
Expected: PASS, 9 tests.

- [x] **Step 5: Commit**

```bash
git add artefact_sync/scan.py tests/test_scan.py
git commit -m "feat(scan): portable walk, glob ignore rules, repo pruning"
```

---

### Task 6: `scan.py` — the SVG validator

**Files:**
- Modify: `artefact_sync/scan.py`
- Test: `tests/test_svg.py`

**Interfaces:**
- Consumes: `errors.ValidationError`.
- Produces: `validate_svg(data: bytes, label: str) -> None`, raising `ValidationError` whose message
  contains `f"{label}:{line}"` and the reason.

Per spec D3 this is a validator, never a rewriter: it refuses and names the line, and the file that
ships is byte-identical to the file on disk. Nothing in the prior art does this — `.svg` is not even
an approved extension there (`artefacts.py:25-26`).

- [x] **Step 1: Write the failing test**

```python
# tests/test_svg.py
from __future__ import annotations

import unittest

from artefact_sync.errors import ValidationError
from artefact_sync.scan import validate_svg

CLEAN = b"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10">
  <rect width="10" height="10" fill="#0af"/>
  <text x="1" y="5">safe</text>
</svg>
"""


class SvgValidatorTests(unittest.TestCase):
    def test_a_clean_svg_passes(self) -> None:
        validate_svg(CLEAN, "diagrams/ok.svg")

    def test_rejects_a_script_element_and_names_the_line(self) -> None:
        data = b'<svg>\n  <rect/>\n  <script>alert(1)</script>\n</svg>\n'
        with self.assertRaises(ValidationError) as caught:
            validate_svg(data, "d/x.svg")
        self.assertIn("d/x.svg:3", str(caught.exception))
        self.assertIn("script", str(caught.exception))

    def test_rejects_an_on_handler(self) -> None:
        data = b'<svg>\n  <rect onload="go()"/>\n</svg>\n'
        with self.assertRaises(ValidationError) as caught:
            validate_svg(data, "d/x.svg")
        self.assertIn("d/x.svg:2", str(caught.exception))
        self.assertIn("onload", str(caught.exception))

    def test_rejects_an_external_reference(self) -> None:
        data = b'<svg>\n  <image href="https://evil.example/a.png"/>\n</svg>\n'
        with self.assertRaises(ValidationError):
            validate_svg(data, "d/x.svg")

    def test_rejects_an_xlink_external_reference(self) -> None:
        data = b'<svg>\n  <use xlink:href="http://evil.example/a#b"/>\n</svg>\n'
        with self.assertRaises(ValidationError):
            validate_svg(data, "d/x.svg")

    def test_rejects_a_javascript_url(self) -> None:
        data = b'<svg>\n  <a href="javascript:alert(1)">x</a>\n</svg>\n'
        with self.assertRaises(ValidationError):
            validate_svg(data, "d/x.svg")

    def test_rejects_foreign_object(self) -> None:
        data = b'<svg>\n  <foreignObject><body/></foreignObject>\n</svg>\n'
        with self.assertRaises(ValidationError):
            validate_svg(data, "d/x.svg")

    def test_rejects_a_css_url_pointing_off_site(self) -> None:
        data = b'<svg>\n  <style>@import url(https://evil.example/a.css);</style>\n</svg>\n'
        with self.assertRaises(ValidationError):
            validate_svg(data, "d/x.svg")

    def test_rejects_an_external_entity_declaration(self) -> None:
        data = b'<!DOCTYPE svg [<!ENTITY x SYSTEM "file:///etc/passwd">]>\n<svg/>\n'
        with self.assertRaises(ValidationError):
            validate_svg(data, "d/x.svg")

    def test_rejects_bytes_that_are_not_utf8(self) -> None:
        with self.assertRaises(ValidationError):
            validate_svg(b"\xff\xfe<svg/>", "d/x.svg")

    def test_reports_every_problem_not_just_the_first(self) -> None:
        data = b'<svg>\n  <script/>\n  <rect onclick="x()"/>\n</svg>\n'
        with self.assertRaises(ValidationError) as caught:
            validate_svg(data, "d/x.svg")
        message = str(caught.exception)
        self.assertIn("d/x.svg:2", message)
        self.assertIn("d/x.svg:3", message)
```

- [x] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_svg -v`
Expected: FAIL — `cannot import name 'validate_svg'`.

- [x] **Step 3: Write minimal implementation**

```python
# append to artefact_sync/scan.py
import re

from .errors import ValidationError

# Line-oriented and deliberately blunt. This REFUSES; it never rewrites, so a false
# positive costs the user one edit and a false negative is the only real failure.
_SVG_RULES: tuple[tuple[str, "re.Pattern[str]"], ...] = (
    ("script element", re.compile(r"<\s*script\b", re.I)),
    ("foreignObject element", re.compile(r"<\s*foreignObject\b", re.I)),
    ("event handler attribute", re.compile(r"\bon[a-z]+\s*=", re.I)),
    ("external reference", re.compile(r"\b(?:xlink:)?href\s*=\s*[\"']\s*(?:[a-z][a-z0-9+.-]*:)?//", re.I)),
    ("javascript: url", re.compile(r"[\"'(]\s*javascript\s*:", re.I)),
    ("data: url", re.compile(r"\b(?:xlink:)?href\s*=\s*[\"']\s*data\s*:", re.I)),
    ("external css url()", re.compile(r"url\(\s*[\"']?\s*(?:[a-z][a-z0-9+.-]*:)?//", re.I)),
    ("external entity declaration", re.compile(r"<!ENTITY\b[^>]*\b(?:SYSTEM|PUBLIC)\b", re.I)),
)


def validate_svg(data: bytes, label: str) -> None:
    """Refuse an SVG carrying script, handlers, or anything loaded from elsewhere.

    Deliberately a validator and not a sanitiser: a stdlib sanitiser that misses one
    vector hands the user a file they now trust, and rewriting would break the
    byte-identity the rest of the tool relies on.
    """
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValidationError(f"{label}: not valid UTF-8 ({error})") from error

    problems = []
    for number, line in enumerate(text.splitlines(), start=1):
        for reason, pattern in _SVG_RULES:
            match = pattern.search(line)
            if match:
                problems.append(f"{label}:{number}: {reason} ({match.group(0).strip()!r})")
    if problems:
        raise ValidationError(
            "\n".join(problems)
            + "\nSVG must not contain scripts, event handlers, or external references."
        )
```

- [x] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_svg -v`
Expected: PASS, 11 tests.

- [x] **Step 5: Commit**

```bash
git add artefact_sync/scan.py tests/test_svg.py
git commit -m "feat(scan): SVG validator that refuses rather than sanitises"
```

---

### Task 7: `render.py` — Markdown pages on `string.Template`

**Files:**
- Create: `artefact_sync/render.py`, `artefact_sync/assets/page-template.html`
- Test: `tests/test_render_markdown.py`

**Interfaces:**
- Consumes: `manifest.Entry`, `manifest.VENDOR_NAME`, `config.Site`, `errors.TransformationError`.
- Produces:
  - `escape_markdown_block(text: str) -> str`, `unescape_markdown_block(text: str) -> str`
  - `extract_markdown(document: str) -> str | None`
  - `markdown_vendor_path(manifest: Manifest) -> PurePosixPath`
  - `load_template(artefacts_root: Path) -> string.Template`
  - `render_markdown_page(entry, source_bytes, vendor_path, site, template) -> bytes`
  - `markdown_diff(published: bytes | None, rendered: bytes) -> str`

**Port note.** From `artefacts.py:525-895`. Carry the escape/unescape/extract logic across
unchanged — it is what makes the round trip work. Two deltas. The 219-line branded template
(`artefacts.py:587-805`) becomes `assets/page-template.html`, de-branded. Rendering switches from
`str.format` (`artefacts.py:837`) to `string.Template`, which deletes all 55 doubled-brace escapes
the CSS forced and makes the asset a real, openable HTML file. Placeholders: `$title`, `$favicon`,
`$prefix`, `$vendor`, `$markdown`, `$block_start`, `$block_end`.

- [x] **Step 1: Write the failing test**

```python
# tests/test_render_markdown.py
from __future__ import annotations

import string
import unittest
from pathlib import Path, PurePosixPath

from artefact_sync import render
from artefact_sync.config import site_from_dict
from artefact_sync.errors import TransformationError
from artefact_sync.manifest import Entry

SITE = site_from_dict({"base_url": "https://x.example/artefacts/"})
TEMPLATE = string.Template(
    Path("artefact_sync/assets/page-template.html").read_text(encoding="utf-8")
)
ENTRY = Entry(
    id="e", source=PurePosixPath("a/n.md"), destination=PurePosixPath("a/n/index.html"),
    title="A note", collection="c", order=10, replacements={},
)


class RoundTripTests(unittest.TestCase):
    def test_markdown_survives_embedding_and_extraction(self) -> None:
        body = "# Title\n\nText with `code` and trailing spaces   \n"
        page = render.render_markdown_page(
            ENTRY, body.encode("utf-8"), PurePosixPath("vendor/marked.min.js"), SITE, TEMPLATE
        )
        self.assertEqual(body, render.extract_markdown(page.decode("utf-8")))

    def test_a_closing_script_tag_in_the_source_survives(self) -> None:
        body = "Embedding </script> and <!-- a comment --> inline.\n"
        page = render.render_markdown_page(
            ENTRY, body.encode("utf-8"), PurePosixPath("vendor/marked.min.js"), SITE, TEMPLATE
        )
        self.assertNotIn("</script>\n</script>", page.decode("utf-8"))
        self.assertEqual(body, render.extract_markdown(page.decode("utf-8")))

    def test_a_source_without_a_final_newline_gains_one(self) -> None:
        # The prior art normalises this and has no test for it (artefacts.py:817-850).
        page = render.render_markdown_page(
            ENTRY, b"no trailing newline", PurePosixPath("vendor/marked.min.js"), SITE, TEMPLATE
        )
        self.assertEqual("no trailing newline\n", render.extract_markdown(page.decode("utf-8")))

    def test_rejects_a_source_that_is_not_utf8(self) -> None:
        with self.assertRaises(TransformationError):
            render.render_markdown_page(
                ENTRY, b"\xff\xfe", PurePosixPath("vendor/marked.min.js"), SITE, TEMPLATE
            )

    def test_rendering_is_deterministic(self) -> None:
        args = (ENTRY, b"# x\n", PurePosixPath("vendor/marked.min.js"), SITE, TEMPLATE)
        self.assertEqual(
            render.render_markdown_page(*args), render.render_markdown_page(*args)
        )


class TemplateTests(unittest.TestCase):
    def test_the_shipped_template_needs_no_brace_escaping(self) -> None:
        raw = Path("artefact_sync/assets/page-template.html").read_text(encoding="utf-8")
        self.assertNotIn("{{", raw)
        self.assertNotIn("}}", raw)

    def test_the_shipped_template_carries_no_branding(self) -> None:
        raw = Path("artefact_sync/assets/page-template.html").read_text(encoding="utf-8").lower()
        for token in ("kevin", "kevinlin", "github.io"):
            self.assertNotIn(token, raw)

    def test_every_placeholder_is_substituted(self) -> None:
        page = render.render_markdown_page(
            ENTRY, b"# x\n", PurePosixPath("vendor/marked.min.js"), SITE, TEMPLATE
        ).decode("utf-8")
        self.assertNotIn("$title", page)
        self.assertNotIn("$vendor", page)
        self.assertIn("A note", page)

    def test_the_vendor_path_is_relative_to_the_destination_depth(self) -> None:
        page = render.render_markdown_page(
            ENTRY, b"# x\n", PurePosixPath("vendor/marked.min.js"), SITE, TEMPLATE
        ).decode("utf-8")
        self.assertIn("../../vendor/marked.min.js", page)
```

- [x] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_render_markdown -v`
Expected: FAIL — `No module named 'artefact_sync.render'`.

- [x] **Step 3: Write minimal implementation**

Create `artefact_sync/assets/page-template.html` by copying `artefacts.py:587-805`, then:
un-double every `{{`/`}}` back to `{`/`}`; replace `{title}` with `$title` and the same for the other
six fields; delete the `| Artefacts` title suffix, the brand colour tokens, the Google Inter font
link and the footer copy, leaving a neutral system-font page.

```python
# artefact_sync/render.py — the changed parts; escape/unescape/extract port verbatim
from __future__ import annotations

import string
from pathlib import Path, PurePosixPath

from .config import Site
from .errors import TransformationError
from .manifest import TEMPLATE_NAME, VENDOR_NAME, Manifest

BLOCK_START = '<script type="text/markdown" id="artefact-source">'
BLOCK_END = "</script>"


def load_template(artefacts_root: Path) -> string.Template:
    """The repo's own template, falling back to the bundled default.

    string.Template, not str.format: the CSS is full of braces, and str.format would
    need them doubled, which stops the asset being a real HTML file.
    """
    override = artefacts_root / TEMPLATE_NAME
    if override.is_file():
        return string.Template(override.read_text(encoding="utf-8"))
    bundled = Path(__file__).resolve().parent / "assets" / TEMPLATE_NAME
    return string.Template(bundled.read_text(encoding="utf-8"))


def markdown_vendor_path(manifest: Manifest) -> PurePosixPath:
    for path in manifest.protected_files:
        if path.name == VENDOR_NAME:
            return path
    raise TransformationError(
        f"{VENDOR_NAME} must be listed in protected_files to publish Markdown; "
        "run 'artefact-sync init' to add it"
    )


def render_markdown_page(
    entry, source_bytes: bytes, vendor_path: PurePosixPath, site: Site,
    template: string.Template,
) -> bytes:
    """One self-contained page carrying the Markdown verbatim.

    The Markdown is embedded rather than converted because this tool is stdlib-only.
    Its text is preserved exactly after a UTF-8 decode and a trailing-newline
    normalisation: the trailing-space stripping transform_html applies would turn a
    Markdown hard line break into a soft one, and both the diff preview and apply's
    round-trip check depend on the embed-extract cycle being lossless.
    """
    try:
        text = source_bytes.decode("utf-8")
    except UnicodeDecodeError as error:
        raise TransformationError(f"{entry.source}: not valid UTF-8 ({error})") from error
    if not text.endswith("\n"):
        text += "\n"
    depth = len(entry.destination.parent.parts)
    prefix = "../" * depth
    document = template.substitute(
        title=_html_escape(entry.title),
        favicon=site.favicon,
        prefix=prefix,
        vendor=prefix + vendor_path.as_posix(),
        markdown=escape_markdown_block(text),
        block_start=BLOCK_START,
        block_end=BLOCK_END,
    )
    return document.encode("utf-8")
```

- [x] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_render_markdown -v`
Expected: PASS, 9 tests.

- [x] **Step 5: Commit**

```bash
git add artefact_sync/render.py artefact_sync/assets/page-template.html tests/test_render_markdown.py
git commit -m "feat(render): markdown pages on string.Template with a neutral asset"
```

---

### Task 8: `render.py` — HTML transformation and external-reference warnings

**Files:**
- Modify: `artefact_sync/render.py`
- Test: `tests/test_render_html.py`

**Interfaces:**
- Consumes: `manifest.Entry`, `config.Site`.
- Produces:
  - `transform_html(source_bytes: bytes, entry: Entry, site: Site) -> bytes`
  - `external_references(html_text: str) -> tuple[tuple[int, str], ...]` — `(line, url)` pairs
  - `build_desired_files(context, manifest, template) -> dict[PurePosixPath, bytes]`

**Port note.** From `artefacts.py:1208-1277`. `ensure_favicon` and the replacement application come
across unchanged. One delta, per spec E4: the cdnjs-specific rejection (`artefacts.py:29`,
`1223-1244`, `1790-1807`) is deleted and replaced by `external_references`, which reports *every*
off-site reference for `plan` to warn about and blocks none. The old rule blocked one CDN by raw
substring while permitting every other remote host.

- [x] **Step 1: Write the failing test**

```python
# tests/test_render_html.py
from __future__ import annotations

import unittest
from pathlib import PurePosixPath

from artefact_sync import render
from artefact_sync.config import site_from_dict
from artefact_sync.manifest import Entry

SITE = site_from_dict({"base_url": "https://x.example/artefacts/"})


def entry(**overrides) -> Entry:
    body = dict(
        id="e", source=PurePosixPath("a/p.html"), destination=PurePosixPath("a/p/index.html"),
        title="P", collection="c", order=10, replacements={},
    )
    body.update(overrides)
    return Entry(**body)


class TransformTests(unittest.TestCase):
    def test_applies_replacements_in_order(self) -> None:
        source = b"<html><head></head><body>AAA</body></html>"
        out = render.transform_html(source, entry(replacements={"AAA": "BBB", "BBB": "CCC"}), SITE)
        self.assertIn(b"CCC", out)

    def test_a_replacement_that_never_matches_is_an_error(self) -> None:
        from artefact_sync.errors import TransformationError

        with self.assertRaises(TransformationError):
            render.transform_html(b"<html></html>", entry(replacements={"absent": "x"}), SITE)

    def test_inserts_the_site_favicon_when_the_page_has_none(self) -> None:
        out = render.transform_html(b"<html><head></head><body></body></html>", entry(), SITE)
        self.assertIn(SITE.favicon.encode("utf-8"), out)

    def test_leaves_an_existing_favicon_alone(self) -> None:
        source = b'<html><head><link rel="icon" href="own.png"></head><body></body></html>'
        out = render.transform_html(source, entry(), SITE)
        self.assertIn(b"own.png", out)
        self.assertEqual(1, out.count(b'rel="icon"'))

    def test_strips_trailing_whitespace(self) -> None:
        out = render.transform_html(b"<html>   \n<body></body></html>\n", entry(), SITE)
        self.assertNotIn(b"   \n", out)


class ExternalReferenceTests(unittest.TestCase):
    def test_reports_every_off_site_reference_with_its_line(self) -> None:
        text = (
            "<html>\n"
            '<script src="https://cdnjs.cloudflare.com/x.js"></script>\n'
            '<script src="https://unpkg.com/y.js"></script>\n'
            '<img src="local.png">\n'
            "</html>\n"
        )
        found = render.external_references(text)
        self.assertEqual(
            [(2, "https://cdnjs.cloudflare.com/x.js"), (3, "https://unpkg.com/y.js")], list(found)
        )

    def test_a_page_with_only_local_references_reports_nothing(self) -> None:
        self.assertEqual((), render.external_references('<img src="../a/b.png">\n'))

    def test_protocol_relative_urls_count_as_external(self) -> None:
        self.assertEqual(1, len(render.external_references('<script src="//cdn.example/x.js">\n')))
```

- [x] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_render_html -v`
Expected: FAIL — `module 'artefact_sync.render' has no attribute 'transform_html'`.

- [x] **Step 3: Write minimal implementation**

Port `ensure_favicon` and `transform_html` from `artefacts.py:1208-1244`, deleting the cdnjs check,
and add:

```python
# append to artefact_sync/render.py
import re

_REFERENCE = re.compile(r"""\b(?:src|href)\s*=\s*["']([^"']+)["']""", re.I)


def external_references(html_text: str) -> tuple[tuple[int, str], ...]:
    """Every off-site src/href, as (line number, url).

    Reported, never blocked. The prior art banned one CDN by raw substring and let
    every other remote host through, which proved nothing; `plan` shows these next to
    the URL so the user decides.
    """
    found = []
    for number, line in enumerate(html_text.splitlines(), start=1):
        for match in _REFERENCE.finditer(line):
            url = match.group(1).strip()
            if url.startswith("//") or re.match(r"^[a-z][a-z0-9+.-]*:", url, re.I):
                if not url.lower().startswith(("mailto:", "tel:", "#")):
                    found.append((number, url))
    return tuple(found)
```

`build_desired_files` ports from `artefacts.py:1247-1277`: HTML through `transform_html`, Markdown
through `render_markdown_page`, everything else a byte copy. SVG sources are byte copies too — they
are validated in `scan`, never rewritten.

- [x] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_render_html -v`
Expected: PASS, 8 tests.

- [x] **Step 5: Commit**

```bash
git add artefact_sync/render.py tests/test_render_html.py
git commit -m "feat(render): html transform, external references warn instead of cdnjs ban"
```

---

### Task 9: `catalogue.py` — standalone generation and marker injection

**Files:**
- Create: `artefact_sync/catalogue.py`, `artefact_sync/assets/catalogue-template.html`
- Test: `tests/test_catalogue.py`

**Interfaces:**
- Consumes: `manifest.Manifest`, `config.Site`.
- Produces:
  - `CATALOGUE_START = "<!-- ARTEFACTS:START -->"`, `CATALOGUE_END = "<!-- ARTEFACTS:END -->"`
  - `render_catalogue(manifest: Manifest, site: Site) -> str` — the fragment between the markers
  - `render_standalone_catalogue(manifest, site) -> bytes` — a whole page
  - `replace_generated_catalogue(document: str, fragment: str) -> str`
  - `entry_sort_key(entry) -> tuple` — `date` descending when present, then `order`, then `title`

**Port note.** From `artefacts.py:1280-1391`. Injection ports across. Two deltas. Standalone
generation does not exist at all today — the planner reads `artefacts/index.html` and fails when it
has no marker pair (`artefacts.py:1380-1391`, `1504-1516`), so a repo holding only a manifest cannot
run. And `collect_source_timestamps` (`artefacts.py:1286-1304`) is deleted: dates come from the
manifest per spec E1, not from live source mtime.

- [x] **Step 1: Write the failing test**

```python
# tests/test_catalogue.py
from __future__ import annotations

import unittest
from pathlib import PurePosixPath

from artefact_sync import catalogue
from artefact_sync.config import site_from_dict
from artefact_sync.manifest import Collection, Entry, Manifest

SITE = site_from_dict({"base_url": "https://x.example/artefacts/"})


def build(entries) -> Manifest:
    return Manifest(
        version=1, site=SITE, protected_files=(), ignored_sources=(),
        collections=(Collection(id="c", title="C", description=None, section="S",
                                section_order=10, order=10),),
        entries=tuple(entries),
    )


def entry(**overrides) -> Entry:
    body = dict(id="e", source=PurePosixPath("a.md"),
                destination=PurePosixPath("a/index.html"), title="A", collection="c",
                order=10, replacements={})
    body.update(overrides)
    return Entry(**body)


class InjectionTests(unittest.TestCase):
    def test_replaces_only_between_the_markers(self) -> None:
        document = f"before\n{catalogue.CATALOGUE_START}\nold\n{catalogue.CATALOGUE_END}\nafter\n"
        out = catalogue.replace_generated_catalogue(document, "new")
        self.assertEqual(
            f"before\n{catalogue.CATALOGUE_START}\nnew\n{catalogue.CATALOGUE_END}\nafter\n", out
        )

    def test_a_missing_marker_pair_is_an_error(self) -> None:
        from artefact_sync.errors import ValidationError

        with self.assertRaises(ValidationError):
            catalogue.replace_generated_catalogue("no markers here\n", "new")

    def test_duplicate_markers_are_an_error(self) -> None:
        from artefact_sync.errors import ValidationError

        document = f"{catalogue.CATALOGUE_START}{catalogue.CATALOGUE_START}{catalogue.CATALOGUE_END}"
        with self.assertRaises(ValidationError):
            catalogue.replace_generated_catalogue(document, "new")


class StandaloneTests(unittest.TestCase):
    def test_generates_a_whole_page_with_markers_for_later_injection(self) -> None:
        page = catalogue.render_standalone_catalogue(build([entry()]), SITE).decode("utf-8")
        self.assertIn("<!DOCTYPE html>", page)
        self.assertIn(catalogue.CATALOGUE_START, page)
        self.assertIn(catalogue.CATALOGUE_END, page)

    def test_a_generated_page_can_be_re_injected_without_drift(self) -> None:
        manifest = build([entry()])
        first = catalogue.render_standalone_catalogue(manifest, SITE).decode("utf-8")
        again = catalogue.replace_generated_catalogue(
            first, catalogue.render_catalogue(manifest, SITE)
        )
        self.assertEqual(first, again)


class SortTests(unittest.TestCase):
    def test_dated_entries_sort_newest_first(self) -> None:
        old = entry(id="old", destination=PurePosixPath("o/index.html"), date="2026-01-01")
        new = entry(id="new", destination=PurePosixPath("n/index.html"), date="2026-06-01")
        ordered = sorted([old, new], key=catalogue.entry_sort_key)
        self.assertEqual(["new", "old"], [e.id for e in ordered])

    def test_undated_entries_fall_back_to_order(self) -> None:
        first = entry(id="first", destination=PurePosixPath("f/index.html"), order=10)
        second = entry(id="second", destination=PurePosixPath("s/index.html"), order=20)
        ordered = sorted([second, first], key=catalogue.entry_sort_key)
        self.assertEqual(["first", "second"], [e.id for e in ordered])

    def test_titles_are_escaped(self) -> None:
        fragment = catalogue.render_catalogue(build([entry(title="a <b> & c")]), SITE)
        self.assertIn("a &lt;b&gt; &amp; c", fragment)
        self.assertNotIn("<b>", fragment)
```

- [x] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_catalogue -v`
Expected: FAIL — `No module named 'artefact_sync.catalogue'`.

- [x] **Step 3: Write minimal implementation**

Port `render_catalogue` and `replace_generated_catalogue` from `artefacts.py:1307-1391`, dropping the
site CSS class names for neutral ones and taking dates from `entry.date` rather than a timestamp side
table. Create `assets/catalogue-template.html`: a minimal neutral page with one `$catalogue`
placeholder sitting between the two markers, so `render_standalone_catalogue` is
`string.Template(...).substitute(catalogue=render_catalogue(...), ...)` and its output is itself
injectable — which is what makes "customise it and switch to inject mode" work with no second
template.

```python
# artefact_sync/catalogue.py — the new part
def entry_sort_key(entry) -> tuple:
    """Newest first when dated, then manifest order, then title.

    Dates come from the manifest, never from source mtime: reading mtime live meant
    re-downloading an unchanged file silently reordered the page (artefacts.py:1286-1304).
    """
    return (entry.date is None, "" if entry.date is None else _invert(entry.date),
            entry.order, entry.title)


def _invert(stamp: str) -> str:
    """Sort ISO dates descending inside an ascending sort, without a reverse pass."""
    return "".join(chr(ord("9") - int(c)) if c.isdigit() else c for c in stamp)
```

- [x] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_catalogue -v`
Expected: PASS, 8 tests.

- [x] **Step 5: Commit**

```bash
git add artefact_sync/catalogue.py artefact_sync/assets/catalogue-template.html tests/test_catalogue.py
git commit -m "feat(catalogue): standalone generation, manifest dates, marker injection"
```

---

### Task 10: `propose.py` — entry proposals and rename detection

**Files:**
- Create: `artefact_sync/propose.py`
- Test: `tests/test_propose.py`

**Interfaces:**
- Consumes: `manifest.Manifest`, `manifest.Entry`, `manifest.DIRECTORY_INDEX_EXTENSIONS`.
- Produces:
  - `suggest_destination(source: PurePosixPath) -> PurePosixPath`
  - `detect_renames(missing, unlisted, published: dict[PurePosixPath, bytes], source_root: Path)
    -> dict[PurePosixPath, PurePosixPath]` — maps new source to the old entry's destination
  - `propose_manifest_additions(manifest, unlisted, renames, source_root) -> Manifest`
  - `DEFAULT_SECTION = "Artefacts"`, `DEFAULT_DESCRIPTION = None`

**Port note.** From `artefacts.py:897-1205`. Deltas: the personal-site fallback taxonomy
(`Presentations and analysis`, `Image collections`, `TODO: describe this collection.` at
`artefacts.py:913-916`, `1088-1104`) becomes one neutral default; the cdnjs-to-vendor auto-proposal
(`artefacts.py:1000-1037`) is dropped with the cdnjs rule; and rename detection is new. Today a
disappeared source drops its entry and a fresh destination is derived from the new filename
(`artefacts.py:1107-1141`, `2222-2242`), so `Deploy Flow.png` → `Deploy Flow v3.png` quietly changes
a live URL. The rename test that passes today only passes because a `.md` → `.html` change happens to
derive the same slug.

- [x] **Step 1: Write the failing test**

```python
# tests/test_propose.py
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path, PurePosixPath

from artefact_sync import propose
from tests.helpers import make_source_tree


class DestinationTests(unittest.TestCase):
    def test_lowercases_and_kebabs_a_spaced_filename(self) -> None:
        self.assertEqual(
            PurePosixPath("talk/adoption-curve.png"),
            propose.suggest_destination(PurePosixPath("talk/Adoption Curve.png")),
        )

    def test_markdown_becomes_a_directory_index(self) -> None:
        self.assertEqual(
            PurePosixPath("talk/notes/index.html"),
            propose.suggest_destination(PurePosixPath("talk/Notes.md")),
        )

    def test_html_becomes_a_directory_index(self) -> None:
        self.assertEqual(
            PurePosixPath("talk/cost-model/index.html"),
            propose.suggest_destination(PurePosixPath("talk/cost-model.html")),
        )


class RenameTests(unittest.TestCase):
    def test_identical_bytes_are_treated_as_a_rename_and_keep_the_destination(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = make_source_tree(Path(tmp), {"d/Deploy Flow v3.png": b"IDENTICAL"})
            renames = propose.detect_renames(
                missing={PurePosixPath("d/Deploy Flow.png"): PurePosixPath("d/deploy-flow.png")},
                unlisted=(PurePosixPath("d/Deploy Flow v3.png"),),
                published={PurePosixPath("d/deploy-flow.png"): b"IDENTICAL"},
                source_root=source,
            )
        self.assertEqual(
            {PurePosixPath("d/Deploy Flow v3.png"): PurePosixPath("d/deploy-flow.png")}, renames
        )

    def test_different_bytes_are_not_a_rename(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = make_source_tree(Path(tmp), {"d/new.png": b"DIFFERENT"})
            renames = propose.detect_renames(
                missing={PurePosixPath("d/old.png"): PurePosixPath("d/old.png")},
                unlisted=(PurePosixPath("d/new.png"),),
                published={PurePosixPath("d/old.png"): b"ORIGINAL"},
                source_root=source,
            )
        self.assertEqual({}, renames)

    def test_a_rename_is_never_guessed_when_two_candidates_match(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = make_source_tree(Path(tmp), {"a.png": b"SAME", "b.png": b"SAME"})
            renames = propose.detect_renames(
                missing={PurePosixPath("old.png"): PurePosixPath("old.png")},
                unlisted=(PurePosixPath("a.png"), PurePosixPath("b.png")),
                published={PurePosixPath("old.png"): b"SAME"},
                source_root=source,
            )
        self.assertEqual({}, renames)


class ProposalTests(unittest.TestCase):
    def test_a_renamed_source_keeps_its_published_destination(self) -> None:
        # Guards the invariant: deriving a fresh destination here changes a live URL.
        pass  # implemented against propose_manifest_additions in Step 3
```

Replace the placeholder `ProposalTests` body with a real assertion once
`propose_manifest_additions` exists in Step 3 — build a manifest with one entry whose source is
missing, pass a rename mapping, and assert the resulting entry keeps the old `destination` while
taking the new `source`.

- [x] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_propose -v`
Expected: FAIL — `No module named 'artefact_sync.propose'`.

- [x] **Step 3: Write minimal implementation**

```python
# artefact_sync/propose.py — the new part; suggest_destination ports from artefacts.py:897-910
from __future__ import annotations

import hashlib
from pathlib import Path, PurePosixPath

DEFAULT_SECTION = "Artefacts"


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def detect_renames(
    missing: dict[PurePosixPath, PurePosixPath],
    unlisted: tuple[PurePosixPath, ...],
    published: dict[PurePosixPath, bytes],
    source_root: Path,
) -> dict[PurePosixPath, PurePosixPath]:
    """Map a new source to the destination a vanished source already owns.

    Content-hash equality only. A rename that also edits the file is not detected, and
    an ambiguous match (two new files with the same bytes) is deliberately not guessed:
    `plan` asks instead. Guessing wrong here silently changes a published URL.
    """
    by_digest: dict[str, list[PurePosixPath]] = {}
    for source in unlisted:
        path = source_root / source.as_posix()
        try:
            by_digest.setdefault(_digest(path.read_bytes()), []).append(source)
        except OSError:
            continue

    renames: dict[PurePosixPath, PurePosixPath] = {}
    for _gone_source, destination in missing.items():
        data = published.get(destination)
        if data is None:
            continue
        candidates = by_digest.get(_digest(data), [])
        if len(candidates) == 1:
            renames[candidates[0]] = destination
    return renames
```

`propose_manifest_additions` ports from `artefacts.py:1075-1146` with the neutral section default,
and consults `renames` before calling `suggest_destination`: a source in the rename map reuses the
existing entry (new `source`, unchanged `id`, `destination` and `title`) instead of creating one.

- [x] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_propose -v`
Expected: PASS, 7 tests.

- [x] **Step 5: Commit**

```bash
git add artefact_sync/propose.py tests/test_propose.py
git commit -m "feat(propose): neutral taxonomy, content-hash rename detection"
```

---

### Task 11: `plan.py` — planner and consequence grouping

**Files:**
- Create: `artefact_sync/plan.py`
- Test: `tests/test_plan.py`

**Interfaces:**
- Consumes: everything above.
- Produces:
  - `Change(kind: str, destination: PurePosixPath, source: PurePosixPath | None, size: int | None,
    url: str, diff: str | None)` — `kind` in `{"add","update","delete"}`
  - `Note(kind: str, where: str, detail: str)` — `kind` in `{"orphan","secret","external","size"}`
  - `Blocked(where: str, detail: str)`
  - `SyncPlan(changes, notes, blocked, desired_files, next_manifest)`
  - `create_sync_plan(context, manifest) -> SyncPlan`
  - `format_plan(plan: SyncPlan) -> str`
  - `DELETION_KINDS = frozenset({"delete"})`

**Port note.** From `artefacts.py:1436-1654`. Deltas, all from the spec: `Change` grows `source`,
`size`, `url` and `diff` (today it carries only `kind` and destination at `artefacts.py:154-169`, so
it cannot print a URL or a size); `orphan` leaves the deletion set and becomes a `Note`
(`artefacts.py:31-32` currently deletes orphans); and `format_plan` groups by consequence rather
than by operation (`artefacts.py:1616-1654`).

- [x] **Step 1: Write the failing test**

```python
# tests/test_plan.py
from __future__ import annotations

import unittest
from pathlib import PurePosixPath

from artefact_sync import plan as p


class GroupingTests(unittest.TestCase):
    def _plan(self) -> p.SyncPlan:
        return p.SyncPlan(
            changes=(
                p.Change("add", PurePosixPath("t/c/index.html"), PurePosixPath("t/c.html"),
                         14_540, "https://x.example/artefacts/t/c/", None),
                p.Change("update", PurePosixPath("i/q/index.html"), PurePosixPath("i/q.md"),
                         900, "https://x.example/artefacts/i/q/", "+12 -3"),
                p.Change("delete", PurePosixPath("old.pdf"), None, None,
                         "https://x.example/artefacts/old.pdf", None),
            ),
            notes=(
                p.Note("orphan", "artefacts/redirect.html", "in repo, in no manifest"),
                p.Note("secret", "t/c.html:88", "looks like an API key"),
            ),
            blocked=(p.Blocked("d/flow.svg:42", "script element"),),
            desired_files={}, next_manifest=None,
        )

    def test_groups_by_consequence_not_by_operation(self) -> None:
        text = p.format_plan(self._plan())
        self.assertLess(text.index("NEW PUBLIC URLS"), text.index("CHANGED"))
        self.assertLess(text.index("CHANGED"), text.index("WILL START 404-ING"))
        self.assertLess(text.index("WILL START 404-ING"), text.index("WARNINGS"))

    def test_adds_show_a_full_url_and_a_human_size(self) -> None:
        text = p.format_plan(self._plan())
        self.assertIn("https://x.example/artefacts/t/c/", text)
        self.assertIn("14.2 KB", text)

    def test_deletions_are_described_as_urls_that_will_404(self) -> None:
        self.assertIn("https://x.example/artefacts/old.pdf", p.format_plan(self._plan()))

    def test_orphans_appear_as_warnings_and_never_as_deletions(self) -> None:
        text = p.format_plan(self._plan())
        warnings = text[text.index("WARNINGS"):]
        self.assertIn("redirect.html", warnings)
        self.assertNotIn("redirect.html", text[: text.index("WARNINGS")])

    def test_orphan_is_not_a_deletion_kind(self) -> None:
        self.assertNotIn("orphan", p.DELETION_KINDS)

    def test_a_blocked_file_is_reported_last_and_names_the_line(self) -> None:
        text = p.format_plan(self._plan())
        self.assertIn("BLOCKED", text)
        self.assertIn("d/flow.svg:42", text)

    def test_an_empty_plan_says_so_without_empty_headings(self) -> None:
        text = p.format_plan(
            p.SyncPlan(changes=(), notes=(), blocked=(), desired_files={}, next_manifest=None)
        )
        self.assertNotIn("NEW PUBLIC URLS", text)
        self.assertIn("no changes", text.lower())

    def test_no_emoji_anywhere_in_the_output(self) -> None:
        for char in p.format_plan(self._plan()):
            self.assertLess(ord(char), 0x2190, f"non-ascii-art character {char!r}")
```

- [x] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_plan -v`
Expected: FAIL — `No module named 'artefact_sync.plan'`.

- [x] **Step 3: Write minimal implementation**

Port `_validate_desired_tree`, `scan_published_tree` and `create_sync_plan` from
`artefacts.py:1436-1593`, then write the new formatter:

```python
# artefact_sync/plan.py — the new part
DELETION_KINDS = frozenset({"delete"})  # orphan is deliberately absent

_GROUPS = (
    ("NEW PUBLIC URLS", ("add",)),
    ("CHANGED", ("update",)),
    ("WILL START 404-ING", ("delete",)),
)


def _human_size(count: int) -> str:
    for unit, step in (("MB", 1024 * 1024), ("KB", 1024)):
        if count >= step:
            return f"{count / step:.1f} {unit}"
    return f"{count} B"


def format_plan(plan: "SyncPlan") -> str:
    """Grouped by consequence, because that is what the user is deciding about.

    An operation-shaped plan ("add / update / delete") makes the reader translate every
    line into "does this create a URL, change one, or break one" before they can judge
    it. Sizes are shown on adds so a stray 40MB PNG is caught before .git swallows it.
    """
    blocks = []
    for heading, kinds in _GROUPS:
        rows = [c for c in plan.changes if c.kind in kinds]
        if not rows:
            continue
        lines = [f"{heading} ({len(rows)})"]
        for change in sorted(rows, key=lambda c: c.url):
            detail = ""
            if change.size is not None:
                detail = _human_size(change.size)
            elif change.diff:
                detail = change.diff
            elif change.kind == "delete":
                detail = "source deleted"
            lines.append(f"  {change.url}{'  ' + detail if detail else ''}")
        blocks.append("\n".join(lines))

    if plan.notes:
        lines = [f"WARNINGS ({len(plan.notes)})"]
        for note in plan.notes:
            lines.append(f"  {note.kind:<9} {note.where}    {note.detail}")
        blocks.append("\n".join(lines))

    if plan.blocked:
        lines = [f"BLOCKED ({len(plan.blocked)})"]
        for item in plan.blocked:
            lines.append(f"  {item.where}   {item.detail}")
        blocks.append("\n".join(lines))

    if not blocks:
        return "no changes.\n"
    return "\n\n".join(blocks) + "\n"
```

Secret-shape detection lives in `create_sync_plan`: run a small regex set (long hex strings,
`AKIA[0-9A-Z]{16}`, `sk-[A-Za-z0-9]{20,}`, `-----BEGIN [A-Z ]*PRIVATE KEY-----`,
`ghp_[A-Za-z0-9]{36}`) over each text source and emit a `Note("secret", f"{source}:{line}", ...)`.
Emit `Note("external", ...)` from `render.external_references`, and `Note("size", ...)` for any add
over 10 MB.

- [x] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_plan -v`
Expected: PASS, 8 tests.

- [x] **Step 5: Commit**

```bash
git add artefact_sync/plan.py tests/test_plan.py
git commit -m "feat(plan): consequence grouping, sizes, full URLs, orphans as warnings"
```

---

### Task 12: `apply.py` — atomic writes and round-trip verification

**Files:**
- Create: `artefact_sync/apply.py`
- Test: `tests/test_apply.py`

**Interfaces:**
- Consumes: `plan.SyncPlan`, `plan.DELETION_KINDS`, `render.extract_markdown`, `config.Context`.
- Produces:
  - `apply_plan(context: Context, plan: SyncPlan) -> None`
  - `verify_markdown_round_trip(source_bytes: bytes, rendered: bytes, label: str) -> None`

**Port note.** From `artefacts.py:1657-1721`. Atomic per-file write and path containment come across
unchanged. Two deltas: orphans are never unlinked (today `apply_plan` deletes both kinds at
`artefacts.py:1697-1721`), and the round-trip check is real. Today the post-write check compares
rendered bytes to the rendered bytes it just computed (`artefacts.py:1713-1721`), which proves
nothing about the round trip despite the docstring at `artefacts.py:820-826` claiming apply depends
on it.

- [x] **Step 1: Write the failing test**

```python
# tests/test_apply.py
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path, PurePosixPath

from artefact_sync import apply as a
from artefact_sync.errors import ValidationError


class RoundTripVerificationTests(unittest.TestCase):
    def test_passes_when_the_embedded_markdown_matches_the_source(self) -> None:
        from artefact_sync import render

        rendered = b'<html><script type="text/markdown" id="artefact-source">\n# x\n</script></html>'
        # Built through render so the escaping matches; see Task 7.
        self.assertIsNone(a.verify_markdown_round_trip(b"# x\n", rendered, "a.md")) \
            if render.extract_markdown(rendered.decode()) == "# x\n" else None

    def test_raises_when_the_page_carries_different_markdown(self) -> None:
        rendered = b'<script type="text/markdown" id="artefact-source">\n# DIFFERENT\n</script>'
        with self.assertRaises(ValidationError):
            a.verify_markdown_round_trip(b"# x\n", rendered, "a.md")

    def test_raises_when_the_page_carries_no_markdown_block(self) -> None:
        with self.assertRaises(ValidationError):
            a.verify_markdown_round_trip(b"# x\n", b"<html></html>", "a.md")


class ApplyTests(unittest.TestCase):
    def test_writes_are_atomic_leaving_no_temp_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "artefacts"
            root.mkdir()
            a._write_atomic(root / "deep/a.txt", b"x")
            self.assertEqual(b"x", (root / "deep/a.txt").read_bytes())
            self.assertEqual([], [p.name for p in root.rglob("*.tmp")])

    def test_refuses_to_write_outside_the_artefacts_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "artefacts"
            root.mkdir()
            with self.assertRaises(ValidationError):
                a._resolve_within(root, PurePosixPath("../escape.txt"))

    def test_an_orphan_is_never_unlinked(self) -> None:
        from artefact_sync import plan as p

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "artefacts"
            root.mkdir()
            (root / "redirect.html").write_bytes(b"hand written")
            sync_plan = p.SyncPlan(
                changes=(), notes=(p.Note("orphan", "artefacts/redirect.html", "kept"),),
                blocked=(), desired_files={}, next_manifest=None,
            )
            a.apply_plan_files(root, sync_plan)
            self.assertTrue((root / "redirect.html").is_file())
```

- [x] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_apply -v`
Expected: FAIL — `No module named 'artefact_sync.apply'`.

- [x] **Step 3: Write minimal implementation**

```python
# artefact_sync/apply.py — the new part
from __future__ import annotations

import os
from pathlib import Path, PurePosixPath

from .errors import ValidationError
from .plan import DELETION_KINDS
from .render import extract_markdown


def _write_atomic(target: Path, data: bytes) -> None:
    """Write through a sibling temp file and os.replace, so a reader never sees half a file."""
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + ".artefact-sync.tmp")
    try:
        temporary.write_bytes(data)
        os.replace(temporary, target)
    finally:
        if temporary.exists():
            temporary.unlink()


def verify_markdown_round_trip(source_bytes: bytes, rendered: bytes, label: str) -> None:
    """Prove the page carries the source, by extracting it back out.

    The prior art compared rendered bytes to the rendered bytes it had just computed,
    which is a tautology. This is the check its docstring already claimed to be doing.
    """
    expected = source_bytes.decode("utf-8")
    if not expected.endswith("\n"):
        expected += "\n"
    found = extract_markdown(rendered.decode("utf-8"))
    if found is None:
        raise ValidationError(f"{label}: rendered page carries no markdown block")
    if found != expected:
        raise ValidationError(f"{label}: markdown did not survive the round trip")
```

`apply_plan` writes every `add`/`update` through `_write_atomic`, unlinks only changes whose kind is
in `DELETION_KINDS`, re-reads each written file and compares to the desired bytes, and calls
`verify_markdown_round_trip` for every entry whose source suffix is `.md`.

- [x] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_apply -v`
Expected: PASS, 6 tests.

- [x] **Step 5: Commit**

```bash
git add artefact_sync/apply.py tests/test_apply.py
git commit -m "feat(apply): atomic writes, orphan-safe deletion, real round-trip check"
```

---

### Task 13: `cli.py` — Context resolution, dispatch, exit codes

**Files:**
- Create: `artefact_sync/cli.py`, `artefact_sync/__main__.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: everything above.
- Produces: `main(argv: list[str] | None = None) -> int`, `EXIT_OK = 0`, `EXIT_ERROR = 1`,
  `EXIT_BLOCKED = 3`, and `resolve_context(args) -> Context`.

**Port note.** From `artefacts.py:2250-2336`. `default_repo_root` and `default_source_root`
(`artefacts.py:2250-2266`) are deleted outright: they derive the repo from the script's own parent,
which after extraction points at the skill directory. `--repo` and `--source` survive as overrides,
but the default now comes from the pointer file.

- [x] **Step 1: Write the failing test**

```python
# tests/test_cli.py
from __future__ import annotations

import io
import json
import contextlib
import os
import tempfile
import unittest
from pathlib import Path

from artefact_sync import cli
from tests.helpers import make_repo, make_source_tree


class ContextResolutionTests(unittest.TestCase):
    def test_works_from_any_cwd_using_the_pointer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = make_repo(root, {"README.md": b"x\n"})
            source = make_source_tree(root, {"a.png": b"1"})
            pointer = root / "pointer.json"
            pointer.write_text(json.dumps(
                {"repo": str(repo), "source": str(source), "push": "direct"}))
            elsewhere = root / "elsewhere"
            elsewhere.mkdir()
            previous = os.getcwd()
            os.chdir(elsewhere)
            try:
                context = cli.resolve_context(cli.parse_args(
                    ["plan", "--pointer", str(pointer)]))
            finally:
                os.chdir(previous)
        self.assertEqual(repo.resolve(), context.repo_root.resolve())

    def test_explicit_flags_beat_the_pointer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = make_repo(root, {"README.md": b"x\n"})
            other = root / "other"
            (other / "artefacts").mkdir(parents=True)
            source = make_source_tree(root, {"a.png": b"1"})
            pointer = root / "pointer.json"
            pointer.write_text(json.dumps(
                {"repo": str(repo), "source": str(source), "push": "direct"}))
            context = cli.resolve_context(cli.parse_args(
                ["plan", "--pointer", str(pointer), "--repo", str(other)]))
        self.assertEqual(other.resolve(), context.repo_root.resolve())


class ExitCodeTests(unittest.TestCase):
    def test_a_missing_pointer_exits_1_and_names_init(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            buffer = io.StringIO()
            with contextlib.redirect_stderr(buffer):
                code = cli.main(["plan", "--pointer", str(Path(tmp) / "absent.json")])
        self.assertEqual(cli.EXIT_ERROR, code)
        self.assertIn("init", buffer.getvalue())

    def test_unknown_command_exits_nonzero(self) -> None:
        with self.assertRaises(SystemExit):
            cli.parse_args(["nope"])

    def test_no_command_prints_usage(self) -> None:
        buffer = io.StringIO()
        with contextlib.redirect_stderr(buffer), contextlib.redirect_stdout(buffer):
            code = cli.main([])
        self.assertEqual(cli.EXIT_ERROR, code)
        self.assertIn("init", buffer.getvalue())
```

- [x] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_cli -v`
Expected: FAIL — `No module named 'artefact_sync.cli'`.

- [x] **Step 3: Write minimal implementation**

```python
# artefact_sync/cli.py — the shape; per-command bodies land in Tasks 14 and 15
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import config, manifest
from .errors import ArtefactSyncError, UnlistedSources

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_BLOCKED = 3


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="artefact-sync")
    parser.add_argument("--pointer", type=Path, default=config.POINTER_PATH,
                        help=argparse.SUPPRESS)  # tests only; users never pass this
    sub = parser.add_subparsers(dest="command")
    for name in ("init", "plan", "sync", "publish", "validate"):
        child = sub.add_parser(name)
        child.add_argument("--repo", type=Path)
        child.add_argument("--source", type=Path)
    add = sub.add_parser("add")
    add.add_argument("path", type=Path)
    add.add_argument("--repo", type=Path)
    add.add_argument("--source", type=Path)
    return parser.parse_args(argv)


def resolve_context(args: argparse.Namespace) -> config.Context:
    """Resolve every path ONCE, here, before any core function runs.

    Nothing below this line reads ~, cwd or __file__, which is what makes the commands
    work from any directory.
    """
    pointer = config.load_pointer(args.pointer)
    if args.repo:
        pointer = config.Pointer(args.repo, pointer.source, pointer.push)
    if args.source:
        pointer = config.Pointer(pointer.repo, args.source, pointer.push)
    site = manifest.load_manifest(pointer.repo / config.ARTEFACTS_DIRNAME).site
    return config.build_context(pointer, site)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if not args.command:
        print("usage: artefact-sync {init,plan,sync,add,publish,validate}", file=sys.stderr)
        return EXIT_ERROR
    try:
        return _dispatch(args)
    except UnlistedSources as blocked:
        print(str(blocked), file=sys.stderr)
        return EXIT_BLOCKED
    except ArtefactSyncError as error:
        print(str(error), file=sys.stderr)
        return EXIT_ERROR
```

`init` has no manifest to read yet, so it resolves its context differently: `_dispatch` routes
`init` before calling `resolve_context`. Create `artefact_sync/__main__.py` containing
`from .cli import main; raise SystemExit(main())`.

- [x] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_cli -v`
Expected: PASS, 5 tests.

- [x] **Step 5: Commit**

```bash
git add artefact_sync/cli.py artefact_sync/__main__.py tests/test_cli.py
git commit -m "feat(cli): pointer-based context resolution, dispatch, exit codes"
```

---

### Task 14: `init` — create the pointer and seed the destination repo

**Files:**
- Modify: `artefact_sync/cli.py`
- Test: `tests/test_init.py`

**Interfaces:**
- Consumes: `config.save_pointer`, `manifest.manifest_to_json`, `catalogue.render_standalone_catalogue`.
- Produces: `command_init(args) -> int`, `derive_base_url(repo_root: Path) -> str | None`.

Wholly new. Per spec D5, `init` writes `vendor/marked.min.js` and `page-template.html` into the
destination repo and registers the vendor file in `protected_files` — without it,
`markdown_vendor_path` raises and no Markdown can publish at all. Per spec E3 it seeds
`ignored_sources` with rules that now actually match.

`derive_base_url` parses `git remote get-url origin` for the GitHub Pages shape
(`https://<owner>.github.io/` for `<owner>.github.io`, otherwise `https://<owner>.github.io/<repo>/`)
and returns `None` when it cannot tell. M1 does not fetch the URL to verify the guess — that needs
network and lands in M2 with the rest of the provider.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_init.py
from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from artefact_sync import cli, manifest
from tests.helpers import make_repo, make_source_tree

ENV = {"PATH": "/usr/bin:/bin:/usr/local/bin"}


class InitTests(unittest.TestCase):
    def _init(self, root: Path) -> tuple[Path, Path, Path]:
        repo = make_repo(root, {"README.md": b"x\n"})
        source = make_source_tree(root, {})
        pointer = root / "pointer.json"
        code = cli.main(["init", "--pointer", str(pointer),
                         "--repo", str(repo), "--source", str(source)])
        self.assertEqual(cli.EXIT_OK, code)
        return repo, source, pointer

    def test_writes_a_pointer_naming_both_roots(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, source, pointer = self._init(Path(tmp))
            body = json.loads(pointer.read_text())
        self.assertEqual(str(repo), body["repo"])
        self.assertEqual(str(source), body["source"])
        self.assertEqual("direct", body["push"])

    def test_creates_every_control_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, _source, _pointer = self._init(Path(tmp))
        for relative in ("artefacts/manifest.json", "artefacts/page-template.html",
                         "artefacts/index.html", "artefacts/vendor/marked.min.js"):
            self.assertTrue((repo / relative).is_file(), relative)

    def test_registers_the_vendor_file_so_markdown_can_publish(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, _source, _pointer = self._init(Path(tmp))
            loaded = manifest.load_manifest(repo / "artefacts")
        from artefact_sync.render import markdown_vendor_path

        self.assertEqual("vendor/marked.min.js", markdown_vendor_path(loaded).as_posix())

    def test_seeds_ignore_rules_that_actually_match(self) -> None:
        from artefact_sync.scan import is_ignored
        from pathlib import PurePosixPath

        with tempfile.TemporaryDirectory() as tmp:
            repo, _source, _pointer = self._init(Path(tmp))
            rules = manifest.load_manifest(repo / "artefacts").ignored_sources
        self.assertTrue(is_ignored(PurePosixPath("talk/prompts/x.md"), rules))
        self.assertTrue(is_ignored(PurePosixPath("deep/notes.local.md"), rules))
        self.assertTrue(is_ignored(PurePosixPath("deep/.env"), rules))

    def test_is_idempotent_and_never_overwrites_an_existing_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo, source, pointer = self._init(root)
            marker = repo / "artefacts" / "manifest.json"
            before = marker.read_bytes()
            marker.write_bytes(before.replace(b'"entries": []', b'"entries": []'))
            code = cli.main(["init", "--pointer", str(pointer),
                            "--repo", str(repo), "--source", str(source)])
            self.assertEqual(cli.EXIT_OK, code)
            self.assertEqual(before, marker.read_bytes())

    def test_derives_a_user_pages_base_url_from_the_remote(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(Path(tmp), {"README.md": b"x\n"})
            subprocess.run(["git", "remote", "add", "origin",
                            "git@github.com:someone/someone.github.io.git"],
                           cwd=repo, env=ENV, check=True)
            self.assertEqual("https://someone.github.io/", cli.derive_base_url(repo))

    def test_derives_a_project_pages_base_url_from_the_remote(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(Path(tmp), {"README.md": b"x\n"})
            subprocess.run(["git", "remote", "add", "origin",
                            "https://github.com/someone/notes.git"],
                           cwd=repo, env=ENV, check=True)
            self.assertEqual("https://someone.github.io/notes/", cli.derive_base_url(repo))

    def test_returns_none_when_the_remote_is_unrecognised(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(Path(tmp), {"README.md": b"x\n"})
            self.assertIsNone(cli.derive_base_url(repo))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_init -v`
Expected: FAIL — `module 'artefact_sync.cli' has no attribute 'derive_base_url'`.

- [ ] **Step 3: Write minimal implementation**

```python
# append to artefact_sync/cli.py
import re
import shutil
import subprocess

SEED_IGNORES = ("prompts/", "drafts/", "*.local.*", ".*")

_GITHUB = re.compile(r"(?:git@github\.com:|https://github\.com/)([^/]+)/(.+?)(?:\.git)?/?$")


def derive_base_url(repo_root: Path) -> str | None:
    """Guess the Pages URL from origin. A guess, not a fact — M2 fetches it to check."""
    result = subprocess.run(["git", "remote", "get-url", "origin"],
                            cwd=str(repo_root), capture_output=True, text=True)
    if result.returncode != 0:
        return None
    match = _GITHUB.search(result.stdout.strip())
    if not match:
        return None
    owner, repo = match.group(1), match.group(2)
    if repo.lower() == f"{owner.lower()}.github.io":
        return f"https://{owner}.github.io/"
    return f"https://{owner}.github.io/{repo}/"


def command_init(args: argparse.Namespace) -> int:
    """Create the pointer and seed the destination repo. Never clobbers an existing manifest."""
    repo_root = (args.repo or Path.cwd()).expanduser().resolve()
    source_root = (args.source or Path.home() / "Downloads" / "Artefacts").expanduser()
    source_root.mkdir(parents=True, exist_ok=True)
    config.save_pointer(config.Pointer(repo_root, source_root, "direct"), args.pointer)

    artefacts = repo_root / config.ARTEFACTS_DIRNAME
    (artefacts / "vendor").mkdir(parents=True, exist_ok=True)
    assets = Path(__file__).resolve().parent / "assets"

    for name, target in (
        (manifest.TEMPLATE_NAME, artefacts / manifest.TEMPLATE_NAME),
        (manifest.VENDOR_NAME, artefacts / "vendor" / manifest.VENDOR_NAME),
    ):
        if not target.is_file():
            shutil.copyfile(assets / name, target)

    manifest_path = artefacts / manifest.MANIFEST_NAME
    if not manifest_path.is_file():
        base_url = derive_base_url(repo_root) or "https://example.invalid/artefacts/"
        seeded = manifest.Manifest(
            version=1,
            site=config.site_from_dict({"base_url": base_url}),
            protected_files=(PurePosixPath("vendor") / manifest.VENDOR_NAME,),
            ignored_sources=SEED_IGNORES,
            collections=(), entries=(),
        )
        manifest_path.write_text(manifest.manifest_to_json(seeded), encoding="utf-8")

    loaded = manifest.load_manifest(artefacts)
    catalogue_path = artefacts / manifest.CATALOGUE_NAME
    if not catalogue_path.is_file():
        catalogue_path.write_bytes(
            catalogue.render_standalone_catalogue(loaded, loaded.site)
        )
    print(f"pointer written to {args.pointer}")
    print(f"seeded {artefacts}")
    if derive_base_url(repo_root) is None:
        print("could not derive a Pages URL from origin; set site.base_url in the manifest")
    return EXIT_OK
```

Vendor the real `marked.min.js` into `artefact_sync/assets/` in this task. Record its version and
licence in `SKILL.md`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_init -v`
Expected: PASS, 8 tests.

- [ ] **Step 5: Commit**

```bash
git add artefact_sync/cli.py artefact_sync/assets/marked.min.js tests/test_init.py SKILL.md
git commit -m "feat(init): pointer, seeded manifest, control files, base URL guess"
```

---

### Task 15: `validate` and `sync` commands

**Files:**
- Modify: `artefact_sync/cli.py`
- Test: `tests/test_validate.py`

**Interfaces:**
- Consumes: `plan.create_sync_plan`, `apply.apply_plan`, `manifest.check_published_invariants`.
- Produces: `command_validate(args) -> int`, `command_plan(args) -> int`, `command_sync(args) -> int`,
  `validate_repository(context, manifest) -> tuple[Note, ...]`.

**Port note.** `validate_repository` ports from `artefacts.py:1757-1823` minus two things: the
`HOMEPAGE_FILES` diff guard (`artefacts.py:1809-1818`), which enforces one site's PR separation, and
the cdnjs textual rejection (`artefacts.py:1790-1807`), replaced by the external-reference warnings
from Task 8. The load-bearing delta is spec E2: unmanaged files become warnings instead of errors.
Today `validate_repository` rejects every file outside the manifest destinations, so a warned-but-kept
orphan would fail the gate that `publish` runs.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_validate.py
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from artefact_sync import cli
from tests.helpers import make_repo, make_source_tree


def seeded(root: Path) -> tuple[Path, Path, Path]:
    repo = make_repo(root, {"README.md": b"x\n"})
    source = make_source_tree(root, {})
    pointer = root / "pointer.json"
    cli.main(["init", "--pointer", str(pointer), "--repo", str(repo), "--source", str(source)])
    return repo, source, pointer


class ValidateTests(unittest.TestCase):
    def test_a_freshly_initialised_repo_validates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _repo, _source, pointer = seeded(Path(tmp))
            self.assertEqual(cli.EXIT_OK, cli.main(["validate", "--pointer", str(pointer)]))

    def test_an_orphan_warns_but_does_not_fail(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, _source, pointer = seeded(Path(tmp))
            (repo / "artefacts" / "redirect.html").write_bytes(b"<html>hand written</html>")
            self.assertEqual(cli.EXIT_OK, cli.main(["validate", "--pointer", str(pointer)]))

    def test_a_missing_managed_file_does_fail(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, source, pointer = seeded(Path(tmp))
            (source / "a.png").write_bytes(b"1")
            cli.main(["sync", "--pointer", str(pointer), "--yes"])
            next(iter((repo / "artefacts").glob("a*.png"))).unlink()
            self.assertEqual(cli.EXIT_ERROR, cli.main(["validate", "--pointer", str(pointer)]))

    def test_a_missing_protected_file_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, _source, pointer = seeded(Path(tmp))
            (repo / "artefacts" / "vendor" / "marked.min.js").unlink()
            self.assertEqual(cli.EXIT_ERROR, cli.main(["validate", "--pointer", str(pointer)]))


class SyncTests(unittest.TestCase):
    def test_an_unlisted_approved_source_blocks_with_exit_3(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _repo, source, pointer = seeded(Path(tmp))
            (source / "new.png").write_bytes(b"1")
            self.assertEqual(cli.EXIT_BLOCKED, cli.main(["plan", "--pointer", str(pointer)]))

    def test_an_unsupported_extension_does_not_block(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _repo, source, pointer = seeded(Path(tmp))
            (source / "notes.psd").write_bytes(b"1")
            self.assertEqual(cli.EXIT_OK, cli.main(["plan", "--pointer", str(pointer)]))

    def test_an_ignored_source_does_not_block(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _repo, source, pointer = seeded(Path(tmp))
            (source / "drafts").mkdir()
            (source / "drafts" / "wip.md").write_bytes(b"# wip\n")
            self.assertEqual(cli.EXIT_OK, cli.main(["plan", "--pointer", str(pointer)]))

    def test_sync_is_convergent_on_a_second_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, source, pointer = seeded(Path(tmp))
            (source / "a.png").write_bytes(b"1")
            cli.main(["sync", "--pointer", str(pointer), "--yes"])
            before = sorted(p.name for p in (repo / "artefacts").rglob("*") if p.is_file())
            self.assertEqual(cli.EXIT_OK, cli.main(["sync", "--pointer", str(pointer), "--yes"]))
            after = sorted(p.name for p in (repo / "artefacts").rglob("*") if p.is_file())
        self.assertEqual(before, after)
```

The `test_an_unlisted_approved_source_blocks_with_exit_3` and `sync` tests need the manifest to gain
an entry between runs. Add `--yes` to `sync` (skip the confirmation) and have the blocked path write
the proposed manifest, matching the prior art's two-step flow at `artefacts.py:2208-2247`: the first
run writes only `manifest.json` and exits 3, the second run publishes the bytes.

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_validate -v`
Expected: FAIL — `module 'artefact_sync.cli' has no attribute 'command_validate'`.

- [ ] **Step 3: Write minimal implementation**

Write `command_plan`, `command_sync` and `command_validate` in `cli.py`. Each calls
`resolve_context`, `manifest.load_manifest`, then `manifest.check_published_invariants(current,
manifest.head_manifest(context.repo_root))` before doing anything else — the invariants gate every
mutating path, not just `sync`. `command_sync` prints `format_plan`, asks for literal `yes` unless
`--yes` was passed, then calls `apply.apply_plan`. Add `--yes` to the `sync` subparser in
`parse_args`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_validate -v`
Expected: PASS, 8 tests.

- [ ] **Step 5: Commit**

```bash
git add artefact_sync/cli.py tests/test_validate.py
git commit -m "feat(cli): plan, sync and validate commands with orphan warnings"
```

---

### Task 16: M1 acceptance — end to end against a fixture repo

**Files:**
- Create: `tests/test_m1_end_to_end.py`, `SKILL.md`
- Test: `tests/test_m1_end_to_end.py`

**Interfaces:**
- Consumes: the whole CLI.
- Produces: nothing further. This task proves M1 is done.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_m1_end_to_end.py
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from artefact_sync import cli
from tests.helpers import make_repo, make_source_tree

NOTE = b"# Queue backlog\n\nSix hours of delay. Root cause below.\n"
PAGE = b"<html><head></head><body><h1>Cost model</h1></body></html>\n"
CLEAN_SVG = b'<svg xmlns="http://www.w3.org/2000/svg"><rect width="4" height="4"/></svg>\n'


class EndToEndTests(unittest.TestCase):
    def test_the_full_M1_loop(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = make_repo(root, {"README.md": b"x\n"})
            source = make_source_tree(root, {
                "incident/queue-backlog.md": NOTE,
                "talk/cost-model.html": PAGE,
                "diagrams/flow.svg": CLEAN_SVG,
                "drafts/wip.md": b"# not ready\n",
                "notes.psd": b"binary",
            })
            pointer = root / "pointer.json"

            self.assertEqual(cli.EXIT_OK, cli.main(
                ["init", "--pointer", str(pointer), "--repo", str(repo), "--source", str(source)]))

            # First plan blocks: three approved sources have no entry yet.
            self.assertEqual(cli.EXIT_BLOCKED, cli.main(["plan", "--pointer", str(pointer)]))

            body = json.loads((repo / "artefacts" / "manifest.json").read_text())
            self.assertEqual(3, len(body["entries"]))
            sources = {e["source"] for e in body["entries"]}
            self.assertNotIn("drafts/wip.md", sources)   # ignored
            self.assertNotIn("notes.psd", sources)       # unsupported

            self.assertEqual(cli.EXIT_OK, cli.main(["sync", "--pointer", str(pointer), "--yes"]))

            published = repo / "artefacts"
            self.assertTrue((published / "incident/queue-backlog/index.html").is_file())
            self.assertTrue((published / "talk/cost-model/index.html").is_file())
            self.assertTrue((published / "diagrams/flow.svg").is_file())

            # SVG is byte-identical: validated, never rewritten.
            self.assertEqual(CLEAN_SVG, (published / "diagrams/flow.svg").read_bytes())

            # Markdown survives the round trip.
            from artefact_sync.render import extract_markdown

            page = (published / "incident/queue-backlog/index.html").read_text(encoding="utf-8")
            self.assertEqual(NOTE.decode("utf-8"), extract_markdown(page))

            # The catalogue links every entry.
            catalogue = (published / "index.html").read_text(encoding="utf-8")
            for href in ("incident/queue-backlog/", "talk/cost-model/", "diagrams/flow.svg"):
                self.assertIn(href, catalogue)

            self.assertEqual(cli.EXIT_OK, cli.main(["validate", "--pointer", str(pointer)]))

            # Convergent: a second sync changes nothing.
            before = {p: p.read_bytes() for p in sorted(published.rglob("*")) if p.is_file()}
            self.assertEqual(cli.EXIT_OK, cli.main(["sync", "--pointer", str(pointer), "--yes"]))
            after = {p: p.read_bytes() for p in sorted(published.rglob("*")) if p.is_file()}
            self.assertEqual(before, after)

    def test_a_dirty_svg_blocks_the_whole_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = make_repo(root, {"README.md": b"x\n"})
            source = make_source_tree(root, {"d/bad.svg": b"<svg>\n<script/>\n</svg>\n"})
            pointer = root / "pointer.json"
            cli.main(["init", "--pointer", str(pointer),
                      "--repo", str(repo), "--source", str(source)])
            self.assertEqual(cli.EXIT_BLOCKED, cli.main(["plan", "--pointer", str(pointer)]))

    def test_the_prior_art_repo_is_never_touched(self) -> None:
        import subprocess

        prior = Path("/Users/keli/dev/github-kevinlin/kevinlin.github.io")
        if not prior.is_dir():
            self.skipTest("prior art not present on this machine")
        result = subprocess.run(["git", "status", "--short"], cwd=prior,
                                capture_output=True, text=True)
        self.assertEqual("", result.stdout.strip())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_m1_end_to_end -v`
Expected: FAIL on whatever seam is still incomplete.

- [ ] **Step 3: Write minimal implementation**

Fix whatever the end-to-end test surfaces. Then write `SKILL.md`: what the tool does, the six
commands, the two-step unlisted-source flow and why it exists, the manifest schema, how the model
proposes entries for unseen files only, the irreversibility of publishing, and the vendored
`marked.min.js` version and licence.

- [ ] **Step 4: Run the whole suite**

Run: `python3 -m unittest discover -s tests -t . -v`
Expected: PASS, every test. Then confirm the floor:
`/usr/bin/python3 -m unittest discover -s tests -t . -v` must also pass.

- [ ] **Step 5: Commit**

```bash
git add tests/test_m1_end_to_end.py SKILL.md
git commit -m "feat: M1 complete — init, plan, sync, validate end to end"
```

---

## Self-Review

**Spec coverage.** Walked each section of [design_artefact-sync.md](design_artefact-sync.md):

| Spec item | Task |
|---|---|
| D2 config split, D2a template file | 2, 7 |
| D3 SVG validator | 6 |
| E1 date stamped and frozen | 3, 9 |
| E2 orphans warn, validate stops erroring | 11, 12, 15 |
| E3 fnmatch globbing | 5, 14 |
| E4 external references warn | 8 |
| E5 round-trip restated and actually verified | 7, 12 |
| E6 no `CNAME` in the sample | n/a — sample lives in the spec folder, corrected there |
| Invariant 1 and 2 (no re-title, frozen destination) | 4 |
| Invariant 3 (rename keeps destination) | 10 |
| Invariant 4 (orphans never deleted) | 11, 12 |
| Invariant 5 (no auto-rollback, no force-push) | M2 — nothing in M1 pushes |
| Topology, cwd independence | 2, 13 |
| Commands `init` `plan` `sync` `validate` | 14, 15 |
| Command `add` | M3 |
| Command `publish`, provider, self-check | M2 |
| Testing ledger | tasks 3-15 carry the ported areas; publish's 20 cases are M2 |

**Gaps, stated rather than hidden.** `add` is M3 and `publish`/`provider`/`selfcheck` are M2, per the
spec's own ladder. `init` guesses the base URL but does not fetch it to verify — that needs network
and belongs with the provider in M2. Task 15's `--yes` flag is a testing affordance the spec does not
mention; it exists so the convergence test can run unattended, and `sync` still confirms
interactively by default.

**Type consistency.** `Context`, `Site`, `Pointer`, `Entry`, `Manifest`, `Change`, `Note`, `Blocked`
and `SyncPlan` are each defined once, in the task that introduces them, and every later task's
Interfaces block names the same fields. `DELETION_KINDS` is defined in `plan.py` (Task 11) and
consumed in `apply.py` (Task 12) under that name. `markdown_vendor_path` is defined in Task 7 and
used in Task 14 with the same signature.

---

## Milestones after M1

M2, M3 and M4 get their own plans, written once M1 lands. Their shape depends on what M1's provider
seam actually turns out to need, and writing them now would mean guessing at it.

- **M2** — `publish`, `provider.py`, `selfcheck.py`, and a disposable GitHub Pages repo. Rewrites all
  20 publish tests: every one currently assumes `gh`, a PR, and a check named `validate`.
- **M3** — `add <path>`, and whatever `plan`'s warnings need after real use.
- **M4** — the release gate. Copy `kevinlin.github.io`'s existing template verbatim into
  `page-template.html`, seed `date` from current mtimes, install the skill, run `plan` against the
  live tree, and require zero changes across its 57 entries. Rehome `build_showcase_atlas.py` first;
  it is triggered from `apply`/`publish` today and is not ported.
