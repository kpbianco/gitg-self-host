#!/usr/bin/env python3
"""Verify or regenerate MANIFEST.tsv from tracked and intended untracked files."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "MANIFEST.tsv"


def paths() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    )
    output = []
    for value in result.stdout.splitlines():
        if value == "MANIFEST.tsv":
            continue
        path = ROOT / value
        if path.is_file():
            output.append(value)
    return sorted(set(output))


def expected_lines() -> list[str]:
    return [f"{name}\t{(ROOT / name).stat().st_size}" for name in paths()]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    expected = expected_lines()
    if args.write:
        MANIFEST.write_text("\n".join(expected) + "\n")
        print(f"Wrote {MANIFEST} with {len(expected)} entries")
        return 0
    actual = MANIFEST.read_text().splitlines() if MANIFEST.exists() else []
    if actual == expected:
        print(f"MANIFEST.tsv verified: {len(expected)} files")
        return 0
    actual_map = {line.split("\t", 1)[0]: line for line in actual if "\t" in line}
    expected_map = {line.split("\t", 1)[0]: line for line in expected}
    missing = sorted(set(expected_map) - set(actual_map))
    stale = sorted(set(actual_map) - set(expected_map))
    changed = sorted(
        name
        for name in set(actual_map) & set(expected_map)
        if actual_map[name] != expected_map[name]
    )
    if missing:
        print("Missing manifest entries:\n  " + "\n  ".join(missing))
    if stale:
        print("Stale manifest entries:\n  " + "\n  ".join(stale))
    if changed:
        print("Wrong byte lengths:\n  " + "\n  ".join(changed))
    print("Run: ./scripts/verify-manifest.py --write", flush=True)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
