#!/usr/bin/env python3
"""Select real Pico board/storage combinations for the full-image matrix."""
import argparse
import json
from pathlib import Path


def select(target):
    rows = json.loads(Path(__file__).with_name('pico-image-targets.json').read_text())
    selected = rows if target == 'all' else [row for row in rows if row['id'] == target]
    if not selected:
        raise ValueError('Unknown Pico image target: ' + target)
    return {'include': selected}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('target')
    args = parser.parse_args()
    print(json.dumps(select(args.target), separators=(',', ':')))
