# What to upload to GitHub

Create a repository named **solar-hosting-capacity-33bus**. Upload the contents of
this folder at the repository root, not the outer ZIP and not a second nested folder.

## Include

- `README.md`, `LICENSE`, `GITHUB_UPLOAD.md`, `CHANGELOG.md`.
- `pyproject.toml`, `requirements-lock.txt`, `requirements-media.txt`, `.gitignore`.
- `src/`, `tests/`, `configs/`, `data/`, `tools/`.
- `reports/` including charts, CSV results, validation evidence and metadata.
- `.github/workflows/tests.yml` (the leading dot folder must be included).
- `media/` including the final MP4, subtitles, script and credits.
- `run-local.ps1`, `release-manifest.json`.

## Do not upload

- `.venv/`, `work/`, downloaded voice models, Python caches or temporary rendered clips.
- The old v0.1.0 archive or the final ZIP inside the repository.
- Passwords, tokens or personal environment files.

The provided GitHub-ready ZIP already excludes temporary files and environments.
Extract it, then upload the files inside `solar-hosting-capacity-33bus/`.
Using Git preserves the `.github` folder reliably. If using the web upload interface,
check that the hidden folder is present after upload. The local launcher is only a
convenience for the original workspace; the README commands are portable.

## Suggested repository description

Reproducible solar voltage-hosting study on a 33-bus feeder, with inverter control,
independent AC validation, sensitivity analysis, tests and a bilingual explainer.

## Suggested topics

`power-systems`, `pandapower`, `python`, `solar-energy`, `distribution-networks`,
`hosting-capacity`, `volt-var`, `electrical-engineering`.

## Release

After uploading and reviewing the files, tag a release `v1.0.0`. Attach the video
or the portable ZIP to the release if desired. Check the Actions tab to confirm
tests actually pass on GitHub. No upload, remote repository or release has been
created automatically by this local project delivery.
