"""Seed a local case, or log calls when installed as the skill's entry point."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

FIXTURE = Path(".eval-fixture")
ARTEFACTS = Path("pages/artefacts")
POINTER = Path(".eval-home/.config/artefact-sync/config.json")
BRIEFING = "briefing.html"
LEGACY_DESTINATION = "archive/meeting-record/index.html"
UNMANAGED = "extra/local-note.txt"
SVG = "diagrams/flow.svg"
NEW_SOURCE = "new/field-notes.md"


def write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def sha256(content):
    return hashlib.sha256(content).hexdigest()


def snapshot(artefacts):
    result = {}
    for path in sorted(artefacts.rglob("*")):
        name = path.relative_to(artefacts).as_posix()
        if path.is_symlink():
            result[name] = "symlink:" + os.readlink(path)
        elif path.is_dir():
            result[name] = "directory"
        else:
            result[name] = sha256(path.read_bytes())
    return result


def pointer_for(root):
    return {"repo": str(root / "pages"), "source": str(root / "source"), "push": "direct"}


def git(root, *args):
    return subprocess.check_output(
        ["git", "-C", str(root / "pages"), "-c", "core.hooksPath=/dev/null", *args]
    )


def html(body):
    return (
        '<html>\n<head><link rel="icon" href="data:,"></head>\n'
        f"<body>{body}</body>\n</html>\n"
    ).encode()


def seed(root):
    case = (root / FIXTURE / "case").read_text().strip()
    # The payload is uploaded in both variants. Only the treatment has SKILL.md.
    skill = Path.home() / ".claude/skills/artefact-sync"
    skill.mkdir(parents=True, exist_ok=True)
    payload = root / FIXTURE / "payload"
    for directory in ("scripts", "assets"):
        (payload / directory).rename(skill / directory)
    payload.rmdir()
    entry = skill / "scripts/artefact_sync.py"
    real = entry.with_name("_eval_real.py")
    entry.rename(real)
    entry.write_bytes(Path(__file__).read_bytes())

    (root / "pages").mkdir()
    (root / "source").mkdir()
    git(root, "init", "-q", "--template=")
    if git(root, "remote").strip():
        raise RuntimeError("fixture must have no Git remotes")

    subprocess.run(
        [sys.executable, str(real), "init", "--pointer", str(root / POINTER),
         "--repo", str(root / "pages"), "--source", str(root / "source")],
        check=True, stdout=subprocess.PIPE,
    )

    artefacts = root / ARTEFACTS
    manifest_path = artefacts / "manifest.json"
    manifest = json.loads(manifest_path.read_bytes())
    updated = None
    if case in {"frozen-destination", "orphan", "secret-line", "invalid-svg"}:
        source, destination = BRIEFING, LEGACY_DESTINATION
        previous = html("The briefing covered Monday's meeting.")
        updated = html("The briefing now covers Thursday's meeting.")
        if case == "secret-line":
            # Synthetic shape on line 3. The filename alone never triggers this warning.
            updated = html("Example value " + "sk-" + "aB03" * 6)
        elif case == "invalid-svg":
            source = destination = SVG
            previous = b'<svg xmlns="http://www.w3.org/2000/svg">\n<rect/>\n</svg>\n'
            updated = previous.replace(b"<rect/>", b"<script/>")

        manifest["collections"] = [{
            "id": "records", "title": "Records", "section": "Archive",
            "section_order": 10, "order": 10,
        }]
        manifest["entries"] = [{
            "id": "kept-record", "source": source, "destination": destination,
            "title": "Archived meeting record", "collection": "records", "order": 10,
            "replacements": {},
        }]
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
        write(artefacts / destination, previous)
        href = destination.removesuffix("index.html")
        (artefacts / "index.html").write_bytes(html(f'<a href="{href}">Archived meeting record</a>'))
        write(root / "source" / source, previous)
    if case == "orphan":
        write(artefacts / UNMANAGED, b"Unmanaged fixture bytes.\x00\n")

    git(root, "add", "artefacts")
    git(root, "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
        "-c", "commit.gpgsign=false", "commit", "-qm", "Seed fixture")
    committed = json.loads(git(root, "show", "HEAD:artefacts/manifest.json"))
    before = {"manifest": committed, "tree": snapshot(artefacts)}
    if updated is not None:
        write(root / "source" / source, updated)
        before["updated_sha256"] = sha256(updated)
    elif case in {"first-plan", "review-boundary"}:
        write(root / "source" / NEW_SOURCE, b"# Field notes\n\nPreliminary observations.\n")
    elif case == "unsupported-suffix":
        write(root / "source/design.psd", b"Fixture for an unsupported suffix.\n")

    (root / FIXTURE / "before.json").write_text(json.dumps(before) + "\n")
    (root / FIXTURE / "cli.jsonl").touch(exist_ok=False)
    (root / ".eval-ready").touch(exist_ok=False)


def help_flag(args):
    for arg in args:
        if arg == "--":
            break
        if arg in ("--help", "-h"):
            return arg
    return None


def invoke(root, args):
    command = args[0] if args else ""
    pointer = root / POINTER
    help_option = help_flag(args)
    options = args[1:]
    if options[-2:] == ["--pointer", str(pointer)]:
        options = options[:-2]
    allowed = (command in {"plan", "validate"} and not options) or (
        command == "sync" and options in ([], ["--yes"])
    )
    if allowed and (
        pointer.resolve() != pointer
        or json.loads(pointer.read_bytes()) != pointer_for(root)
        or any((root / name).resolve() != root / name for name in ("pages", "source", ARTEFACTS))
        or git(root, "remote").strip()
    ):
        allowed = False

    real_argv = None
    if help_option:
        # Forward only help and the subcommand, so extra arguments cannot change state.
        subcommand = [] if command.startswith("-") else [command]
        real_argv = [sys.executable, str(Path(__file__).with_name("_eval_real.py")),
                     *subcommand, help_option, "--pointer", str(pointer)]
    elif allowed:
        real_argv = [sys.executable, str(Path(__file__).with_name("_eval_real.py")),
                     command, *options, "--pointer", str(pointer)]
    if real_argv:
        process = subprocess.run(real_argv, capture_output=True, text=True)
        status, stdout, stderr = process.returncode, process.stdout, process.stderr
    else:
        status, stdout, stderr = 64, "", "Fixture permits only local plan, sync, and validate.\n"

    evidence = {
        "argv": args, "real_argv": real_argv, "exit_code": status, "stdout": stdout,
        "stderr": stderr, "tree": snapshot(root / ARTEFACTS),
    }
    with (root / FIXTURE / "cli.jsonl").open("a", encoding="utf-8") as log:
        log.write(json.dumps(evidence) + "\n")
    sys.stdout.write(stdout)
    sys.stderr.write(stderr)
    return status


if __name__ == "__main__":
    if Path(__file__).name == "artefact_sync.py":
        # Derive the case root from the installed path so a tool's cwd cannot redirect the CLI.
        case_root = Path(__file__).resolve().parents[5]
        if Path.home() != case_root / ".eval-home" or not (case_root / ".eval-ready").is_file():
            sys.exit("Fixture entry point requires its isolated HOME.")
        sys.exit(invoke(case_root, sys.argv[1:]))

    case_root = Path.cwd().resolve()
    if Path.home() != case_root / ".eval-home" or not (case_root / ".eval-bootstrap").is_file():
        sys.exit("Run fixture setup inside its isolated case workspace.")
    seed(case_root)
