<p align="center">
  <img src="assets/icons/icon-192x192.png" alt="artefact-sync" width="128" height="128">
</p>

<h1 align="center">artefact-sync</h1>

<p align="center">
  A Claude Code skill that publishes local files to your GitHub Pages site<br>
  and never changes a URL you already shared.
</p>

---

## What this is for

You make things in whatever project you happen to be working in: a diagram, a talk deck, an
incident writeup. You want them on the internet at a stable address. You do not want to hand-edit
a site repo. And you really do not want last month's shared link to start 404-ing because a file
got renamed.

`artefact-sync` one-way syncs one local folder into the `artefacts/` tree of one GitHub Pages repo.
A `manifest.json` inside that repo records which source file publishes to which URL, and the tool
treats every mapping it has published as frozen:

- A published `destination` never changes. Rename the source file and the URL stays.
- An existing entry is never re-titled or re-slugged.
- Files in the site that the manifest doesn't know about are reported, never deleted or rewritten.
- Nothing new goes public until you've read its proposed URL and said yes.

It's Python 3 stdlib only, runs on stock macOS `python3`, and talks to `git` and `gh` as binaries.
No dependencies, no venv, no server.

<img src="assets/icons/favicon-32x32.png" alt="" width="18" height="18" align="top"> **Not** a
site generator, a two-way sync, or a CMS. It moves approved files into a site you already have.

## Quick start

**1. Install the skill**

```bash
git clone https://github.com/kevinlin/artefact-sync.git ~/.claude/skills/artefact-sync
```

**2. Point it at your Pages repo and your source folder** (once per machine)

```bash
python3 "$HOME/.claude/skills/artefact-sync/scripts/artefact_sync.py" \
  init --repo ~/dev/you.github.io --source ~/Downloads/Artefacts
```

`init` writes a machine-local pointer to `~/.config/artefact-sync/config.json`, seeds
`artefacts/manifest.json`, `page-template.html`, `index.html` and `vendor/marked.min.js` in the repo
if they're missing, guesses your Pages URL from the git remote, and fetches it once to check the
guess. It never overwrites an existing manifest.

**3. Drop a file in the source folder, then look before you leap**

```bash
cp ~/Desktop/cost-model.md ~/Downloads/Artefacts/
python3 "$HOME/.claude/skills/artefact-sync/scripts/artefact_sync.py" plan
```

The first `plan` for a file it hasn't seen exits `3` and writes one thing: a *proposed* manifest
entry with a slug, a title and a collection. No bytes, no page. That's deliberate: you read the
URL it wants to create, edit it if you disagree, and only then continue.

```
NEW PUBLIC URLS (1)
  https://you.github.io/artefacts/cost-model/            14.2 KB

WARNINGS (1)
  secret    cost-model.md:88    looks like an API key
```

**4. Write the files, then make them live**

```bash
python3 "$HOME/.claude/skills/artefact-sync/scripts/artefact_sync.py" sync      # local writes
python3 "$HOME/.claude/skills/artefact-sync/scripts/artefact_sync.py" publish   # commit, push, verify
```

`publish` refuses to start unless the tree is clean outside `artefacts/` and your branch matches
`origin`. It commits, pushes, waits for the Pages build, then fetches every published URL to prove
it worked. **Publishing is irreversible in practice** — search engines and readers cache a URL, and
deleting the file later doesn't undo that.

In Claude Code you can skip the paths entirely and just ask: *"sync my artefacts"*, *"add this
diagram to my site"*. The skill's [SKILL.md](SKILL.md) is the contract the agent follows.

## Commands

| Command | Does |
|---|---|
| `init` | Configure the repo and source folder; seed missing control files |
| `plan` | Show new URLs, changed content, URLs that would start 404-ing, warnings, blocked files |
| `sync` | Recompute the plan, confirm, apply atomic per-file writes locally |
| `add <path>` | Copy one file into the source folder and sync that entry |
| `validate` | Offline check of manifest, file set, catalogue links, local references, SVG policy |
| `publish` | Self-check, validate, apply, commit, push, wait for the build, verify every URL |

Approved types: `.html` `.md` `.png` `.jpeg` `.jpg` `.ico` `.pdf` `.webp` `.gif` `.svg`. SVG is
validated and copied byte-for-byte — a `<script>` inside one is rejected by line number, never
silently stripped.

Warnings (`secret`, `external`, `orphan`, `size`) print next to the change groups and never stop a
run. An `EXCLUDED` block lists what was in the folder and didn't sync, so "where did my file go" has
an answer on the same screen.

## Where things live

| Where | Holds |
|---|---|
| `~/.claude/skills/artefact-sync/` | this repo: code, page template, vendored `marked.min.js`, icons |
| `~/.config/artefact-sync/config.json` | `repo`, `source`, `push` (machine-local, survives `git pull`) |
| `<your repo>/artefacts/` | `manifest.json`, `page-template.html`, `index.html`, `vendor/`, the published tree |

The manifest lives with the site on purpose. Reinstall the skill, switch laptops, delete
`~/.config`. None of it can break a link you already published.

## Already publishing an `artefacts/` tree?

You can adopt the skill without touching a single existing URL. [SKILL.md](SKILL.md#adopting-an-existing-artefacts-tree)
has the six-step order; the short version is that `plan` must end up reporting no changes at all,
and any file it wants to rewrite is a rendering difference to explain *before* you sync.

## Development

```bash
python3 -m unittest discover -s tests -t .            # 246 tests, ~11s
/usr/bin/python3 -m unittest discover -s tests -t .   # macOS stock 3.9.6 — the version floor
```

Both interpreters, every time. [CLAUDE.md](CLAUDE.md) has the constraints that have a test behind
them; [docs/specs/design_artefact-sync.md](docs/specs/design_artefact-sync.md) is authoritative on
behaviour and records why each design call was made.
