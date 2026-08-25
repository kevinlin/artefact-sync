# Changelog

What shipped in `artefact-sync`. Releases are git tags; `SKILL.md`'s `metadata.version` names the
current one. Within a release the entries are the milestones that built it, newest first, each
linking to its plan under [docs/specs/](docs/specs/). Those plans carry the task breakdown, the
deviations, and the corrections each milestone applied back to the design.

---

## 1.0.0 — 2026-08-25

First public release. M1 through M4 built it: the portable core, `publish`, `add`, and a release
gate that required zero rewrites of an already-published tree. 245 tests pass on 3.9.6 and 3.13.

### Layout — the agent-skill folder convention (2026-08-25)

The skill root now holds `SKILL.md` and the conventional folders: `assets`, `docs`, `scripts`,
`tests`. No behaviour changed; 245 tests pass on 3.9.6 and 3.13, as before.

- The `artefact_sync/` package flattened into `scripts/`. The fourteen modules import each other by
  bare name, because running a file in `scripts/` puts that directory on `sys.path`.
- `scripts/artefact_sync.py` is the entry point, replacing `__main__.py`. Invocation is
  `python3 "$HOME/.claude/skills/artefact-sync/scripts/artefact_sync.py" <command>` from any
  directory, with no `PYTHONPATH`. The two documented forms became one.
- Bundled templates and vendored JS moved from `artefact_sync/assets/` to `assets/`. The four
  `__file__`-relative lookups collapsed into `config.ASSETS`.
- `tests/__init__.py` puts `scripts/` on the path the same way, so the test command is unchanged:
  `python3 -m unittest discover -s tests -t .`. `test_stdlib_only` derives its sibling-module
  allowance from the directory listing.
- The completed M1-M4 plans still describe the old layout. They record what was done at the time, so
  they were left alone.

---

### M4 — release gate against a probe pair (2026-08-25)

[plan](docs/specs/plan_artefact-sync-m4.md) · [acceptance](docs/specs/m4-acceptance.md) · 245 tests

The gate: publish a tree with the prior art, adopt it with the skill, require zero rewrites. That
procedure found four defects, each of which silently rewrote published content, plus one adoption
blocker that stopped the first run dead.

- **Line endings normalise on decode.** `render.normalise_source_text` decodes UTF-8, rewrites CRLF
  and lone CR to LF, and guarantees a trailing newline. Without it, `core.autocrlf=input` stores
  bytes that differ from the ones `apply` wrote, and a fresh clone reports the same entry changed on
  every run, forever.
- **`$vendor` carries the vendor path alone.** `$prefix` is the `../` climb, and a template composes
  `src="$prefix$vendor"`. The old renderer baked the climb into `$vendor`, so a template using both
  doubled it.
- **The embedded block matches what the prior art published:**
  `<script type="text/markdown" id="markdown-source">` plus a newline. The old spelling rewrote
  every Markdown page an adopter had, and `extract_markdown` could read none of them.
- **The catalogue emits styleable markup.** `render_catalogue` uses the `card-grid`, `card` and
  `card-updated` classes a host page's CSS already targets. Cards sort by newest entry date
  descending, stable on `order`; entries inside a card keep sorting by `order`, because that
  position is editorial.
- **`head_manifest` tolerates a HEAD manifest predating the `site` block.** It injects a placeholder
  and returns `None` on any parse failure, which keeps the URL-freeze guard alive on exactly the run
  where published destinations are at stake.
- Live probe: 11 verified URLs, `.svg` and `.pdf` through the two-step propose-then-publish flow, a
  dirty SVG rejected by line number, and a deletion reconverged.

Migrating `kevinlin.github.io` became a follow-on rather than the gate. It still needs
`site.catalogue.section_links` and a new home for the atlas build.

### M3 — `add`, and plan output that tells the whole truth (2026-08-24)

[plan](docs/specs/plan_artefact-sync-m3.md) · 227 tests

- **`add <path>`.** Stages one file into the source folder and runs the same plan-confirm-apply cycle
  `sync` runs, with the named file's proposal pre-accepted. Refuses a collision, an unapproved
  extension, an ignored path, and a directory. Every other unlisted source still blocks.
- **The orphan warning stops naming files the run deletes.** It used to promise "left alone" about a
  file it was deleting in the same breath.
- **A root-level collection is called `General`**, not named after whichever file sorts first.
- **The private-name heuristic matches at any word boundary.** `Client Presentation.pdf`,
  `Internal Notes.html` and `q1-internal-review.md` all passed silently before. `plan.source_warnings`
  became a public seam, with tests.
- **`plan` prints an `EXCLUDED` block** for the unsupported and ignored files it had been computing
  and throwing away, and orders warnings deterministically.

The orphan warning and the collection name came out of M2's live run. No test caught either.

### M2 — `publish` (2026-08-23)

[plan](docs/specs/plan_artefact-sync-m2.md) · [acceptance](docs/specs/m2-acceptance.md)

- **`provider.py`**, the single seam to the outside world: `git` and `gh` through an injectable
  `CommandRunner`, HTTP through `urllib`. Nothing else in the package talks to a process or a socket.
- **`publish.py`**: self-check, preflight, recompute, confirm, apply, validate, commit, push, build
  wait, URL verification. Preflight refuses any tracked change outside `artefacts/`, a non-default
  branch, or a branch diverged from origin.
- **Two push modes.** `direct` commits and pushes the default branch. `branch` cuts a timestamped
  branch, prints the compare URL, and stops without making anything live.
- **URL verification covers `protected_files`**, so a green publish now proves the vendored
  `marked.min.js` is reachable. The prior art never checked.
- **`selfcheck.py`**, a sub-second install integrity check: asset sizes, both template
  substitutions, one Markdown round trip. It exists for the corrupted `git pull`, which no CI run
  can see.
- **`init` fetches the base URL it guessed**, so a wrong guess surfaces at init rather than at
  publish.
- `validate.py` was lifted out of `cli.py` unchanged, breaking the import cycle that would have
  blocked `publish` from validating.
- Nothing force-pushes and nothing rolls back. A failed push names the local commit and the retry
  command.

The acceptance run against a disposable Pages repository passed all fifteen rows and exposed two M1
defects, both deferred to M3 by name.

### M1 — the portable core (2026-08-22)

[plan](docs/specs/plan_artefact-sync-m1.md) · 131 tests

Extracted `scripts/artefacts.py` from `kevinlin.github.io` into a stdlib-only package with no
network path. `init`, `plan`, `sync` and `validate` run against a local repository.

- **`cli.py` resolves `(repo_root, source_root, site)` once** into a frozen `Context` before
  dispatch. No function below the CLI reads `~`, `cwd` or `__file__`, which is what makes "works from
  any directory" true rather than aspirational.
- **Three state locations, one owner each:** the skill directory holds code and bundled assets;
  `~/.config/artefact-sync/config.json` holds the machine-local pointer; `<repo>/artefacts/` holds
  the manifest, the page template, the catalogue and the published tree.
- **Published-URL invariants, enforced against `git show HEAD:artefacts/manifest.json`:** an existing
  entry is never re-titled or re-slugged, a `destination` is frozen once published, and a source
  rename keeps its destination. A rename is detected by content hash; when hashes do not match,
  `plan` asks rather than guessing.
- **`plan` groups by consequence**, not by operation: new public URLs with byte sizes, changed
  content with diffs, URLs that will start 404-ing, warnings, blocked files. Full URLs, spelled out.
  It exits 3 when blocked, writing the proposed manifest and nothing else, which is what makes the
  two-step flow work.
- **Orphans warn and are never deleted.** An unmanaged file might be a hand-written page or a
  redirect.
- **The page template became a real file** on `string.Template`, so its CSS needs no brace escaping
  and the file previews in a browser. `$title`, `$favicon`, `$prefix`, `$vendor`, `$markdown`,
  `$block_start`, `$block_end`.
- **Standalone catalogue generation**, which the prior art had no path for: it could not run at all
  in a repository whose catalogue shell was missing.
- **The SVG validator rejects and names the line; it never rewrites.** A stdlib sanitiser that misses
  `foreignObject`, `xlink:href` or CSS `url()` is worse than none, because the user then trusts it.
- **The allowlist gained `.pdf`, `.webp`, `.gif` and `.svg`.** The cdnjs ban generalised into a
  warning on any external reference in published HTML.
- **`ignored_sources` gained `fnmatch` globbing.** Matching was exact-string or literal `dir/`
  prefix, so a seeded `*.local.*` rule would have matched nothing and published the files it was
  meant to hide.
- `apply` gained a real round-trip check: extract the embedded Markdown and compare it to the source.
  It used to compare rendered bytes to the rendered bytes it had just computed.
