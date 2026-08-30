# Rolex AI v3.0.1

Android-first, local-first personal AI shell built with Kivy.

## Build strategy

The APK runtime intentionally uses only `python3` and `kivy==2.3.1` as mandatory Python-for-Android requirements. Optional document readers are imported lazily by `main.py`, so missing desktop-only parser dependencies do not stop the Android build.

Target: **arm64-v8a**, Android API 34, minimum API 23, NDK 25b.

## Local build

```bash
buildozer android debug
```

## GitHub Actions

Push the project to a GitHub repository and push to `main`. The workflow at `.github/workflows/android.yml` builds the debug APK and uploads it as the `RolexAI-debug-arm64` artifact.

## Important

No build can honestly be guaranteed to succeed on every machine or future dependency mirror. This package is designed to remove the known failure points from the earlier Android builds: excessive Python dependencies, unsupported optional parsers in the APK requirement list, missing workflow verification, and architecture mismatch.
