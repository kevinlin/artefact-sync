from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path, PurePosixPath

import apply as apply_module
import catalogue, config, manifest, plan as plan_module, provider, publish, selfcheck
import validate
from errors import ArtefactSyncError, ConfigError, UnlistedSources

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_BLOCKED = 3
SEED_IGNORES = ("prompts/", "drafts/", "*.local.*", ".*")


def _add_context_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--pointer", type=Path, default=config.POINTER_PATH,
                        help=argparse.SUPPRESS)
    parser.add_argument("--repo", type=Path)
    parser.add_argument("--source", type=Path)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="artefact-sync")
    sub = parser.add_subparsers(dest="command")
    for name in ("init", "plan", "sync", "publish", "validate"):
        child = sub.add_parser(name)
        _add_context_args(child)
        if name == "sync":
            child.add_argument("--yes", action="store_true")
    add = sub.add_parser("add")
    add.add_argument("path", type=Path)
    add.add_argument("--yes", action="store_true")
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


def command_init(args: argparse.Namespace) -> int:
    repo_root = (args.repo or Path.cwd()).expanduser().resolve()
    if not repo_root.is_dir():
        raise ConfigError(f"repository directory does not exist: {repo_root}")
    source_root = (args.source or Path.home() / "Downloads" / "Artefacts").expanduser().resolve()
    source_root.mkdir(parents=True, exist_ok=True)
    config.save_pointer(config.Pointer(repo_root, source_root, "direct"), args.pointer)

    artefacts = repo_root / config.ARTEFACTS_DIRNAME
    (artefacts / "vendor").mkdir(parents=True, exist_ok=True)
    assets = config.ASSETS
    for name, target in (
        (manifest.TEMPLATE_NAME, artefacts / manifest.TEMPLATE_NAME),
        (manifest.VENDOR_NAME, artefacts / "vendor" / manifest.VENDOR_NAME),
    ):
        if not target.is_file():
            shutil.copyfile(assets / name, target)

    guessed_url = provider.derive_base_url(repo_root)
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
    else:
        _report_base_url(loaded.site.base_url)
    return EXIT_OK


def _report_base_url(base_url: str) -> None:
    """Fetch the configured base URL once, so a wrong guess surfaces now, not at publish."""
    status = provider.fetch(base_url)
    if status == 200:
        print(f"verified {base_url}")
    elif status == 0:
        print(f"warning: {base_url} did not respond; check site.base_url in the manifest")
    else:
        print(f"warning: {base_url} returned {status}; check site.base_url in the manifest "
              "and that Pages is enabled for this repository")


def _command_state(
    args: argparse.Namespace,
) -> tuple[config.Context, manifest.Manifest]:
    context = resolve_context(args)
    current = manifest.load_manifest(context.artefacts_root)
    manifest.check_published_invariants(current, manifest.head_manifest(context.repo_root))
    return context, current


def _write_proposed_manifest(context: config.Context, sync_plan: plan_module.SyncPlan) -> bool:
    if sync_plan.next_manifest is None or not any(
        item.detail.startswith("approved source has no manifest entry")
        for item in sync_plan.blocked
    ):
        return False
    body = manifest.manifest_to_json(sync_plan.next_manifest).encode("utf-8")
    apply_module.write_atomic(context.artefacts_root / manifest.MANIFEST_NAME, body)
    return True


def command_plan(args: argparse.Namespace) -> int:
    context, current = _command_state(args)
    sync_plan = plan_module.create_sync_plan(context, current)
    print(plan_module.format_plan(sync_plan), end="")
    if sync_plan.blocked:
        _write_proposed_manifest(context, sync_plan)
        return EXIT_BLOCKED
    return EXIT_OK


def _apply_or_report(
    args: argparse.Namespace,
    context: config.Context,
    sync_plan: plan_module.SyncPlan,
    verb: str,
) -> int:
    print(plan_module.format_plan(sync_plan), end="")
    if sync_plan.blocked:
        _write_proposed_manifest(context, sync_plan)
        return EXIT_BLOCKED
    if not args.yes and input("Apply these changes? Type yes to continue: ") != "yes":
        print(f"{verb} cancelled; nothing was applied.")
        return EXIT_ERROR
    apply_module.apply_plan(context, sync_plan)
    return EXIT_OK


def command_sync(args: argparse.Namespace) -> int:
    context, current = _command_state(args)
    return _apply_or_report(args, context, plan_module.create_sync_plan(context, current), "sync")


def _source_relative(context: config.Context, given: Path) -> PurePosixPath:
    """Where `given` will live, relative to the source root."""
    resolved = given.resolve()
    root = context.source_root.resolve()
    if resolved.is_relative_to(root):
        return PurePosixPath(resolved.relative_to(root).as_posix())
    return PurePosixPath(resolved.name)


def command_add(args: argparse.Namespace) -> int:
    context, current = _command_state(args)
    given = args.path.expanduser()
    if given.is_symlink() or not given.is_file():
        raise ConfigError(f"not a regular file: {given}")
    if given.suffix.lower() not in manifest.APPROVED_EXTENSIONS:
        raise ConfigError(
            f"{given.suffix or given.name} is not an approved type; approved: "
            + " ".join(sorted(manifest.APPROVED_EXTENSIONS))
        )
    relative = _source_relative(context, given)
    if manifest.is_ignored(relative, current.ignored_sources):
        raise ConfigError(
            f"{relative.as_posix()} matches an ignored_sources rule and would never sync; "
            "rename it or edit ignored_sources in the manifest"
        )
    target = context.source_root / relative.as_posix()
    if target.resolve() != given.resolve():
        if target.exists() or target.is_symlink():
            raise ConfigError(
                f"{target} already exists; rename the file, or edit it in place and run sync"
            )
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(given, target)
        print(f"copied {relative.as_posix()} into {context.source_root}")
    sync_plan = plan_module.create_sync_plan(context, current, accepted=(relative,))
    return _apply_or_report(args, context, sync_plan, "add")


def command_validate(args: argparse.Namespace) -> int:
    context, current = _command_state(args)
    for note in validate.validate_repository(context, current):
        print(f"warning: {note.kind} {note.where}: {note.detail}")
    return EXIT_OK


def command_publish(args: argparse.Namespace) -> int:
    context, current = _command_state(args)
    selfcheck.run_self_check(context.artefacts_root)
    try:
        result = publish.publish(context, current)
    except publish.BlockedPlan as blocked:
        _write_proposed_manifest(context, blocked.plan)
        print(str(blocked), file=sys.stderr)
        return EXIT_BLOCKED
    if result is None:
        return EXIT_OK
    print(f"published {result.commit[:12]} on {result.branch}")
    if result.verified_url_count:
        print(f"verified {result.verified_url_count} published URLs "
              f"under {result.catalogue_url}")
    return EXIT_OK


def _dispatch(args: argparse.Namespace) -> int:
    if args.command == "init":
        return command_init(args)
    commands = {
        "add": command_add,
        "plan": command_plan,
        "sync": command_sync,
        "publish": command_publish,
        "validate": command_validate,
    }
    command = commands.get(args.command)
    if command is None:
        raise ConfigError(f"{args.command} command is not available yet")
    return command(args)


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
