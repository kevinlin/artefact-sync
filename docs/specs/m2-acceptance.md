# M2 acceptance: publish against a disposable Pages repository

Status: not yet run
Date: <fill in>

The unit suite runs `publish` against a recorded fake world, which proves orchestration and nothing
else. Auth, push, build timing, URL derivation and deletion are exactly what the fake mocks out.
This run is their only coverage. Do it against a throwaway repository, never against a site with
published URLs.

## Setup

1. Create a public repository `artefact-sync-probe` under your account. Do not reuse a real one.
2. Enable Pages: Settings, Pages, source `Deploy from a branch`, branch `main`, folder `/ (root)`.
3. `git clone` it, and commit one `index.html` so the branch exists and Pages has something to build.
4. `mkdir ~/Downloads/ProbeArtefacts`.

## Steps

| # | Command | Expected | Result |
|---|---|---|---|
| 1 | `python3 -m artefact_sync init --repo <clone> --source ~/Downloads/ProbeArtefacts` | Prints the pointer path, seeds `artefacts/`, and either `verified https://<you>.github.io/artefact-sync-probe/artefacts/` or a warning that it is not live yet | |
| 2 | Confirm the guess: does the printed base URL match the URL in the repository's Pages settings, with `artefacts/` on the end? | Yes | |
| 3 | Put four files in the source folder: a `.md`, an `.html`, a `.png`, and a clean `.svg` | | |
| 4 | `python3 -m artefact_sync plan` | Exit 3, four proposals written to `artefacts/manifest.json`, four full URLs printed with byte sizes | |
| 5 | Read the proposed destinations and titles, edit if wrong | | |
| 6 | `python3 -m artefact_sync publish`, type `yes` | Preflight passes, four URLs listed in the confirmation, apply, validate, commit, push, build wait, then every URL verified | |
| 7 | Record the wall-clock time of the build wait | Under five minutes, or `BUILD_POLL_ATTEMPTS` needs raising | |
| 8 | Open each published URL in a browser | The Markdown page renders through `marked.js`; the image and SVG load; the catalogue links all four | |
| 9 | `python3 -m artefact_sync publish` again with nothing changed | `nothing to publish`, every URL re-verified, no commit | |
| 10 | Delete the `.png` from the source folder, then `publish` | The confirmation says one URL will start returning 404; after the build, that URL 404s and the other three still serve | |
| 11 | `gh auth logout`, then `publish` | Refuses in preflight, names `gh auth login`, changes nothing | |
| 12 | `gh auth login`, edit an unrelated file at the repository root, then `publish` | Refuses, names that file, changes nothing | |
| 13 | Set `"push": "branch"` in the pointer, change a source file, then `publish` | Pushes `artefact-sync/<timestamp>`, prints the compare URL, verifies nothing, leaves `main` untouched | |
| 14 | Merge that branch by hand, then `publish` on `main` | Preflight requires a `git pull --ff-only` first, and says so | |
| 15 | Delete the probe repository and the source folder | | |

## Result

<fill in: what passed, what did not, and what changed as a result>
