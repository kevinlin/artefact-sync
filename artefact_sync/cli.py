from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import config, manifest
from .errors import ArtefactSyncError, ConfigError, UnlistedSources

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_BLOCKED = 3


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
