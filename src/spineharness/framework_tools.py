"""Install current standalone framework CLIs and freeze their resolved versions."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

SPEC_KIT_REPO = "https://github.com/github/spec-kit.git"
SPEC_KIT_SOURCE = "git+" + SPEC_KIT_REPO
OPEN_SPEC_PACKAGE = "@fission-ai/openspec@latest"
VERSION = re.compile(r"v(\d+)\.(\d+)\.(\d+)\Z")
SHA = re.compile(r"[0-9a-f]{40}\Z")
OPEN_SPEC_VERSION = re.compile(r"\d+\.\d+\.\d+\Z")


def command(argv: list[str], *, timeout: int = 300) -> str:
    try:
        result = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, check=True)
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        detail = getattr(exc, "stderr", "") or getattr(exc, "stdout", "") or str(exc)
        raise RuntimeError(f"Framework setup failed at {argv[0]}: {str(detail).strip()[-2000:]}") from exc
    return result.stdout.strip()


def latest_spec_kit() -> tuple[str, str]:
    """Choose the highest stable release tag and resolve it to an immutable commit."""
    output = command(["git", "ls-remote", "--tags", SPEC_KIT_REPO])
    tags: dict[str, dict[str, str]] = {}
    for line in output.splitlines():
        commit, _, ref = line.partition("\t")
        if not SHA.fullmatch(commit) or not ref.startswith("refs/tags/"):
            continue
        name = ref.removeprefix("refs/tags/")
        peeled = name.endswith("^{}")
        if peeled:
            name = name[:-3]
        if VERSION.fullmatch(name):
            tags.setdefault(name, {})["commit" if peeled else "ref"] = commit
    if not tags:
        raise ValueError("Spec Kit has no stable release tags")
    tag = max(tags, key=lambda value: tuple(map(int, VERSION.fullmatch(value).groups())))
    return tag, tags[tag].get("commit") or tags[tag]["ref"]


def setup() -> dict[str, str]:
    tag, commit = latest_spec_kit()
    source = f"{SPEC_KIT_SOURCE}@{commit}"
    command(["uvx", "--refresh", "--from", source, "specify", "version"], timeout=600)
    command(["npm", "install", "--global", OPEN_SPEC_PACKAGE], timeout=600)
    version = command(["openspec", "--version"], timeout=30)
    if not OPEN_SPEC_VERSION.fullmatch(version):
        raise ValueError(f"OpenSpec returned an invalid version: {version!r}")
    return {"speckit_tag": tag, "speckit_ref": source, "openspec_version": version}


def save(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(data, indent=2) + "\n")
    temporary.replace(path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, help="Four-arm config to fill with resolved tool pins")
    parser.add_argument("--manifest", type=Path, help="Reference-study tool manifest to create")
    args = parser.parse_args()
    if (args.config is None) == (args.manifest is None):
        parser.error("Provide exactly one of --config or --manifest")
    if args.config:
        from .framework_matrix import load

        config = load(args.config, require_tool_pins=False)
        if Path(config["results_dir"]).exists() or Path(config["work_dir"]).exists():
            parser.error("This attempt already has work or results; use a fresh configuration")
        raw = json.loads(args.config.read_text())
        resolved = setup()
        raw.update(resolved)
        save(args.config, raw)
    else:
        if args.manifest.exists():
            resolved = json.loads(args.manifest.read_text())
            installed = command(["openspec", "--version"], timeout=30)
            if installed != resolved["openspec_version"]:
                parser.error("Installed OpenSpec changed; use a fresh WORK_DIR for a new tool resolution")
        else:
            resolved = setup()
            save(args.manifest, resolved)
    print(json.dumps(resolved, indent=2))


if __name__ == "__main__":
    main()
