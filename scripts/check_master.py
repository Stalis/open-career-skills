#!/usr/bin/env python3
"""Check recorded source fingerprints in a master resume."""
import argparse
import hashlib
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PATTERN = re.compile(r'^- `([^`]+)` `([0-9a-f]{64})`$', re.M)


def check(path):
    text = path.read_text(encoding='utf-8')
    records = PATTERN.findall(text)
    if not records:
        raise ValueError('No source fingerprints found')
    changed = []
    for name, expected in records:
        target = (ROOT / name).resolve()
        if not target.is_relative_to(ROOT) or not target.is_file():
            changed.append(name)
        elif hashlib.sha256(target.read_bytes()).hexdigest() != expected:
            changed.append(name)
    return changed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('resume', type=Path)
    args = parser.parse_args()
    try:
        changed = check(args.resume)
    except (OSError, ValueError) as exc:
        parser.exit(2, f'Cannot verify: {exc}\n')
    if changed:
        parser.exit(1, 'STALE: source changed or missing: ' + ', '.join(changed) + '\n')
    print('CURRENT: recorded sources match; this does not verify claims or review status')


if __name__ == '__main__': main()
