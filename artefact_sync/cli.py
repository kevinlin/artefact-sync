from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path, PurePosixPath

from . import catalogue, config, manifest
from .errors import ArtefactSyncError, ConfigError, UnlistedSources

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_BLOCKED = 3
SEED_IGNORES = ("prompts/", "drafts/", "*.local.*", ".*")
_GITHUB = re.compile(r"(?:git@github\.com:|https://github\.com/)([^/]+)/(.+?)(?:\.git)?/?$")


def _add_context_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--pointer", type=Path, default=config.POINTER_PATH,
                        help=argparse.SUPPRESS)
    parser.add_argument("--repo", type=Path)
    parser.add_argument("--source", type=Path)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="artefact-sync")
    sub = parser.add_subparsers(dest="command")
    for name in ("init", "plan", "sync", "publish", "validate"):
        _add_context_args(sub.add_parser(name))
    add = sub.add_parser("add")
    add.add_argument("path", type=Path)
    _add_context_args(add)
    return parser.parse_args(argv)


def resolve_context(args: argparse.Namespace) -> config.Context:
    pointer = config.load_pointer(args.pointer)
    if args.repo:
        pointer = config.Pointer(args.repo, pointer.source, pointer.push)
    if args.source:
        pointer = config.Pointer(pointer.repo, args.source, pointer.push)
    site = manifest.load_manifest(pointer.repo / config.ARTEFACTS_DIRNAME).site
    return config.build_context(pointer, site)


def derive_base_url(repo_root: Path) -> str | None:
    result = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
    )
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
    repo_root = (args.repo or Path.cwd()).expanduser().resolve()
    if not repo_root.is_dir():
        raise ConfigError(f"repository directory does not exist: {repo_root}")
    source_root = (args.source or Path.home() / "Downloads" / "Artefacts").expanduser().resolve()
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

    guessed_url = derive_base_url(repo_root)
    manifest_path = artefacts / manifest.MANIFEST_NAME
    if not manifest_path.is_file():
        seeded = manifest.Manifest(
            version=1,
            site=config.site_from_dict(
                {"base_url": guessed_url or "https://example.invalid/artefacts/"}
            ),
            protected_files=(PurePosixPath("vendor") / manifest.VENDOR_NAME,),
            ignored_sources=SEED_IGNORES,
            collections=(),
            entries=(),
        )
        manifest_path.write_text(manifest.manifest_to_json(seeded), encoding="utf-8")

    loaded = manifest.load_manifest(artefacts)
    catalogue_path = artefacts / manifest.CATALOGUE_NAME
    if not catalogue_path.is_file():
        catalogue_path.write_bytes(catalogue.render_standalone_catalogue(loaded, loaded.site))
    print(f"pointer written to {args.pointer}")
    print(f"seeded {artefacts}")
    if guessed_url is None:
        print("could not derive a Pages URL from origin; set site.base_url in the manifest")
    return EXIT_OK


def _dispatch(args: argparse.Namespace) -> int:
    if args.command == "init":
        command = globals().get("command_init")
        if command is None:
            raise ConfigError("init command is not implemented")
        return command(args)
    resolve_context(args)
    raise ConfigError(f"{args.command} command is not implemented")


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
