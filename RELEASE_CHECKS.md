# Local release verification — v1.0.0

- Core study completed: six placement/control combinations and eight sensitivity cases.
- Nine pytest tests passed after the final core implementation.
- All Python source and production scripts compiled successfully.
- Editable package wheel built and installed successfully using the project metadata.
- Independent radial solver checked against pandapower at 54 operating points.
- Baseline and study reports generated from saved simulation outputs.
- Study run metadata records the exact study source SHA-256 and library versions.
- Video rendered locally: H.264, 1920×1080, 24 fps; AAC stereo narration; about 112 seconds.
- Entire video and audio streams decoded successfully with FFmpeg (exit code 0).
- Subtitle font coverage checked programmatically; rendered Arabic and English
  frames visually reviewed. Arabic uses Tajawal Bold with font-aware shaping.
- Repository ZIP excludes caches, virtual environments, voice-model binaries,
  temporary video renders and the obsolete baseline-only archive.
- Delivery manifest includes SHA-256 hashes for repository files.

Numerical limitations are retained in the report, including unresolved high-capacity
control points. Hosted GitHub CI has not run and the repository has not been published.
