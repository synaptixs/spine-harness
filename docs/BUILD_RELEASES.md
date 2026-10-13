# Build portable release archives

Run these commands from a Spine Harness source checkout on macOS with Python 3.12, Git, and a local Spine checkout containing tag `v3.57.1`. The builder verifies that the tag points to the pinned Spine commit, checks package contents for credential patterns and local machine paths, and writes a ZIP plus a `.zip.sha256` file. Packaging makes no model calls.

```bash
export PYTHONPATH="$PWD/src"
python3.12 -m spineharness.build_portable_release \
  --platform macos \
  --spine-source /absolute/path/to/spine \
  --output dist
python3.12 -m spineharness.build_portable_release \
  --platform windows \
  --spine-source /absolute/path/to/spine \
  --output dist
```

The current builder produces `dist/spineharness-macos-2026-10-13-v21.zip` and `dist/spineharness-windows-wsl2-2026-10-13-v21.zip`, with a checksum file beside each archive. The Windows archive runs Python and Codex inside WSL2 Ubuntu; native Windows Python is not supported. The Windows/WSL2 workflow still needs live validation on a Windows machine. See the [release validation record](releases/RELEASE_VALIDATION_V21.md) for the checks already performed.

Verify the outer ZIPs and checksums from the source checkout:

```bash
(cd dist && shasum -a 256 -c spineharness-macos-2026-10-13-v21.zip.sha256)
(cd dist && shasum -a 256 -c spineharness-windows-wsl2-2026-10-13-v21.zip.sha256)
unzip -t dist/spineharness-macos-2026-10-13-v21.zip
unzip -t dist/spineharness-windows-wsl2-2026-10-13-v21.zip
```

Each extracted package also contains `SHA256SUMS` for its files. Run `shasum -a 256 -c SHA256SUMS` from the extracted macOS package, or `sha256sum -c SHA256SUMS` inside WSL2 Ubuntu for the Windows package. The Windows package includes `verify_package.py` for an additional local verification step.

`dist/` is generated output and is ignored by Git. Keep only the archives and checksum files needed for delivery in that folder; regenerate them from source when needed. Older packages remain available through repository history, but are not maintained as source files. The builder uses a fixed release version, so rebuilding the same platform in the same output directory replaces that platform's existing ZIP and checksum.
