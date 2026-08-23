# M2 acceptance: publish against a disposable Pages repository

Status: run and passed
Date: 2026-08-23

The unit suite runs `publish` against a recorded fake world, which proves orchestration and nothing
else. Auth, push, build timing, URL derivation and deletion are exactly what the fake mocks out.
This run is their only coverage. Do it against a throwaway repository, never against a site with
published URLs.

Run against `kevinlin/artefact-sync-probe`, a public repository created for this run and deleted at
row 15. Live URL: `https://kevinlin.github.io/artefact-sync-probe/artefacts/`. Four source files:
`probe-note.md`, `probe-page.html`, `probe-curve.png` (7,855 bytes, generated), `probe-shape.svg`.

## Setup

1. Create a public repository `artefact-sync-probe` under your account. Do not reuse a real one.
2. Enable Pages: Settings, Pages, source `Deploy from a branch`, branch `main`, folder `/ (root)`.
3. `git clone` it, and commit one `index.html` so the branch exists and Pages has something to build.
4. `mkdir ~/Downloads/ProbeArtefacts`.

## Steps

| # | Command | Expected | Result |
|---|---|---|---|
| 1 | `python3 -m artefact_sync init --repo <clone> --source ~/Downloads/ProbeArtefacts` | Prints the pointer path, seeds `artefacts/`, and either `verified https://<you>.github.io/artefact-sync-probe/artefacts/` or a warning that it is not live yet | Pass. Seeded `manifest.json`, `page-template.html`, `index.html`, `vendor/marked.min.js`; warned `returned 404`, correct — nothing was published there yet |
| 2 | Confirm the guess: does the printed base URL match the URL in the repository's Pages settings, with `artefacts/` on the end? | Yes | Pass. Pages reports `https://kevinlin.github.io/artefact-sync-probe/`; the guess is that plus `artefacts/`. This is correction M1-a proving itself — M1's guess would have been short by one segment, and every seeded URL wrong |
| 3 | Put four files in the source folder: a `.md`, an `.html`, a `.png`, and a clean `.svg` | | Done. The `.md` deliberately carries `$dollar`, a literal `</script>`, an em dash, an HTML entity and a fenced code block |
| 4 | `python3 -m artefact_sync plan` | Exit 3, four proposals written to `artefacts/manifest.json`, four full URLs printed with byte sizes | Pass. Exit 3, four proposals, four URLs with sizes (`7.7 KB`, `6.0 KB`, `250 B`, `314 B`) |
| 5 | Read the proposed destinations and titles, edit if wrong | | Done, and it earned its place. All four root-level sources landed in one collection *named after the alphabetically first file*, `probe-curve` — `propose._source_group` returns `""` for a root-level file, so the label falls through to `sources[0].stem`. Grouping is right, the name is arbitrary. Renamed the collection to `probe` / "Probe artefacts" and retitled one entry, to prove hand edits survive publish. See "What the run found" |
| 6 | `python3 -m artefact_sync publish`, type `yes` | Preflight passes, four URLs listed in the confirmation, apply, validate, commit, push, build wait, then every URL verified | Pass. Confirmation named all four new URLs and the irreversibility; commit `d5c82269abd4` on `main`; `verified 6 published URLs` — the four entries, the catalogue, and `vendor/marked.min.js`. The protected file is in that count, which is the gap this design set out to close |
| 7 | Record the wall-clock time of the build wait | Under five minutes, or `BUILD_POLL_ATTEMPTS` needs raising | Pass, with room to spare. 39 seconds for the whole command — plan, apply, validate, commit, push, build wait and six fetches. `BUILD_POLL_ATTEMPTS = 60` (five minutes) stands |
| 8 | Open each published URL in a browser | The Markdown page renders through `marked.js`; the image and SVG load; the catalogue links all four | Pass, checked in a real browser. The Markdown page renders through `marked.js` with zero console messages, and every awkward character survives the round trip: `$dollar`, the literal `</script>`, the em dash, the `café` entity, the fenced block, the list. The catalogue lists all four with the hand-edited collection title. The SVG renders. The `.png` and `.svg` bytes served are sha256-identical to the source bytes, which is stronger than the status-code check `publish` itself does |
| 9 | `python3 -m artefact_sync publish` again with nothing changed | `nothing to publish`, every URL re-verified, no commit | Pass. `no changes.` / `nothing to publish; 6 published URLs verified.`, no new commit |
| 10 | Delete the `.png` from the source folder, then `publish` | The confirmation says one URL will start returning 404; after the build, that URL 404s and the other three still serve | Pass on behaviour, with a defect in the output. The confirmation named exactly one URL; after the build `probe-curve.png` returns 404, the other three serve 200, and the catalogue dropped its link. But the same plan run also warned `orphan artefacts/probe-curve.png — in repo, in no manifest, left alone` about the very file it was deleting. See "What the run found" |
| 11 | `gh auth logout`, then `publish` | Refuses in preflight, names `gh auth login`, changes nothing | Pass, by substitution. `gh auth logout` cannot be undone without an interactive browser login, so this row ran with a stub `gh` earlier on `PATH` whose `auth status` exits 1 — the same preflight branch, the same code path. Refused with `the GitHub CLI is not authenticated: ...` and `gh auth login`, exit 1, no commit |
| 12 | `gh auth login`, edit an unrelated file at the repository root, then `publish` | Refuses, names that file, changes nothing | Pass. `the working tree has changes outside artefacts/: index.html`, with a `git stash push -- index.html` recovery naming the file. Exit 1, no commit |
| 13 | Set `"push": "branch"` in the pointer, change a source file, then `publish` | Pushes `artefact-sync/<timestamp>`, prints the compare URL, verifies nothing, leaves `main` untouched | Pass. Pushed `artefact-sync/20260823-091346`, printed the `compare/main...` URL, no build wait, no URL verification, `origin/main` unmoved. The `.md` change showed as a unified diff in the plan. Note the checkout is left on the pushed branch; the next `publish` refuses with `git switch main` as its recovery, which is how you get back |
| 14 | Merge that branch by hand, then `publish` on `main` | Preflight requires a `git pull --ff-only` first, and says so | Pass. Merged as PR #1 on GitHub, so local `main` fell behind. `publish` refused: `local main and origin/main have diverged (0 ahead, 2 behind)` and named `git pull --ff-only origin main`. Following that recovery and re-running gave `nothing to publish; 5 published URLs verified` — the failure converges, which is the claim the design makes and never tested |
| 15 | Delete the probe repository and the source folder | | See "Teardown" |

## What the run found

Two defects, neither in M2's own code, both surfaced only because a real publish ran.

**The orphan warning contradicts the deletion it accompanies.** In `plan.create_sync_plan`, the
orphan scan is `scan_published_tree(artefacts_root) - expected`, and `expected` does not subtract
the destinations already queued as `delete` changes. So a file being deleted in this very run is
also reported as `in repo, in no manifest, left alone`. The behaviour is correct — `apply` acts on
changes, not on notes, and row 10 confirmed the file really goes — but the sentence is false as
printed. It matters more than a cosmetic slip: design invariant 4 makes "orphans are never deleted"
a promise to the user, and printing that promise about a file being deleted is exactly the case
where a user needs the output to be trustworthy. One line fixes it, plus a test.

**`propose` names a root-level collection after its alphabetically first file.** Row 5. Grouping
every root-level source into one collection is right; calling that collection `probe-curve` because
`probe-curve.png` sorts first is not. Only the first run is arbitrary — the collection is in the
manifest by the second — but the first run is the one a new user sees.

Both belong to M3, which the plan already scopes as "`add <path>`, and whatever `plan`'s warnings
need after the Task 9 run exposes them". Neither was fixed here; expanding M2 to cover them would
put untested changes into the milestone whose whole point was to get one tested end-to-end run.

## Teardown

`~/Downloads/ProbeArtefacts`, the local clone and the pointer at
`~/.config/artefact-sync/config.json` were all removed. The `artefact-sync-probe` repository itself
could not be deleted from here: the authenticated `gh` token carries `gist`, `read:org`, `repo` and
`workflow`, and repository deletion needs `delete_repo`, which can only be added through an
interactive `gh auth refresh -h github.com -s delete_repo`. Delete it by hand:

    gh auth refresh -h github.com -s delete_repo
    gh repo delete kevinlin/artefact-sync-probe --yes

## Result

Passed. Fifteen rows, no row failed, and no code change was forced.

What this run covers that the 195 unit tests cannot: real `gh` authentication, a real push to a real
remote, real Pages build timing (39 seconds, against a five-minute budget), URL derivation against a
live Pages host, and a real deletion becoming a real 404. Every one of those is mocked out by the
recorded fake world, and every one worked first time.

Two things exceeded the checklist and are worth keeping in the next run: the `.png` and `.svg` bytes
served were sha256-compared against the source bytes and matched, closing by hand the gap the design
records as "nothing verifies that the bytes GitHub serves equal the bytes pushed"; and row 14's
printed recovery was followed to the end, proving a failed publish converges on a re-run rather than
merely claiming to.
