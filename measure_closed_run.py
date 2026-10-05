"""Run the user's shared token calculator on CLOSED isolated benchmark sessions.

Only the input root and verified price snapshot are adapted in memory. The shared
calculator itself is not modified. Run after all benchmark children have exited.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import sys
import tempfile
from pathlib import Path

import harness_config as C
from codex_usage import PRICES


def main():
    path = Path.home() / ".claude/tools/session-tokens.py"
    spec = importlib.util.spec_from_file_location("shared_session_tokens", path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"Shared calculator unavailable: {path}")
    calculator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(calculator)
    calculator.CODEX_SESSIONS = C.CODEX_LOGIN_HOME / "sessions"
    calculator.OPENAI_PRICES.update(PRICES)
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--model")
    parser.add_argument("--measured-only", action="store_true",
                        help="Use exported arm sessions, excluding diagnostic attempts")
    options, args = parser.parse_known_args()
    session_copy = None
    if options.measured_only:
        if not options.model:
            raise SystemExit("--measured-only requires --model")
        session_copy = tempfile.TemporaryDirectory(prefix="spineharness-accounting-")
        root = Path(session_copy.name)
        target = root / "2026" / "09" / "29"
        target.mkdir(parents=True)
        model_dir = C.RESULTS_DIR / options.model
        patterns = ("speckit/*/session-rollout-*.jsonl", "spine/pass*/codex-calls/*/rollout-*.jsonl",
                    "intake/pass*-calls/*/rollout-*.jsonl")
        for pattern in patterns:
            for file in model_dir.glob(pattern):
                name = file.name.removeprefix("session-")
                shutil.copy2(file, target / name)
        calculator.CODEX_SESSIONS = root
    if options.model:
        original_find = calculator._codex_files_for
        def selected_files(project):
            selected = []
            for file, session in original_find(project):
                models = set()
                for line in file.read_text().splitlines():
                    try:
                        row = json.loads(line)
                    except ValueError:
                        continue
                    if row.get("type") == "turn_context":
                        models.add(row.get("payload", {}).get("model"))
                if models == {options.model}:
                    selected.append((file, session))
            return selected
        calculator._codex_files_for = selected_files
    if "--until" not in args:
        raise SystemExit("Pass --since <UTC start> --until <UTC end> after the benchmark closes")
    sys.argv = [str(path), "--tool", "codex", "--project", str(C.WORK_DIR), *args]
    calculator.main()
    if session_copy:
        session_copy.cleanup()


if __name__ == "__main__":
    main()
