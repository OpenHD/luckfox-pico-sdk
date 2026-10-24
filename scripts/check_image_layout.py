#!/usr/bin/env python3
"""Check that SDK partition metadata matches the raw ImageWriter disk layout."""
import argparse
from pathlib import Path
import re


def byte_size(value):
    match = re.fullmatch(r'(0x[0-9a-fA-F]+|[0-9]+)([KMG]?)', value)
    if not match:
        raise ValueError('Invalid partition size: ' + value)
    return int(match[1], 16 if match[1].startswith('0x') else 10) * {
        '': 1, 'K': 1024, 'M': 1024**2, 'G': 1024**3}[match[2]]


def check_layout(board_text, image_text):
    assignment = re.search(r'^export RK_PARTITION_CMD_IN_ENV="([^"]+)"', board_text, re.M)
    if not assignment:
        raise ValueError('Board config does not declare RK_PARTITION_CMD_IN_ENV')
    board = {}
    end = 0
    definitions = assignment[1].split(',')
    for index, definition in enumerate(definitions):
        match = re.fullmatch(r'([^@()]+)(?:@([^()]+))?\(([^()]+)\)', definition)
        if not match:
            raise ValueError('Invalid board partition: ' + definition)
        size, offset, name = match.groups()
        if name in board:
            raise ValueError('Duplicate board partition: ' + name)
        start = byte_size(offset) if offset else end
        if start < end:
            raise ValueError('Overlapping board partition: ' + name)
        length = None if size == '-' else byte_size(size)
        if length is None and (name != 'RECORDINGS' or index != len(definitions) - 1):
            raise ValueError('Only the final RECORDINGS partition may grow')
        board[name] = (start, length)
        if length is not None:
            end = start + length

    image_names = []
    end = 0
    for name, body in re.findall(r'\bpartition\s+(\w+)\s*\{([^{}]*)\}', image_text):
        if name not in board:
            raise ValueError('Image partition missing from board config: ' + name)
        values = dict(re.findall(r'^\s*(size|offset)\s*=\s*(\S+)', body, re.M))
        offset = byte_size(values['offset']) if 'offset' in values else end
        length = byte_size(values['size']) if 'size' in values else board[name][1]
        if offset != board[name][0]:
            raise ValueError(f'{name}: board offset {board[name][0]} differs from image offset {offset}')
        if board[name][1] is not None and length != board[name][1]:
            raise ValueError(f'{name}: board size {board[name][1]} differs from image size {length}')
        if length is None or length <= 0:
            raise ValueError('Image partition has no fixed positive size: ' + name)
        if offset < end:
            raise ValueError('Overlapping image partition: ' + name)
        end = offset + length
        image_names.append(name)
    if image_names != list(board):
        raise ValueError('Board and image partition order/inventory differ')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('board_config', type=Path)
    parser.add_argument('image_config', type=Path)
    args = parser.parse_args()
    try:
        check_layout(args.board_config.read_text(), args.image_config.read_text())
    except ValueError as error:
        parser.exit(1, f'Image layout mismatch: {error}\n')
    print('Board partition metadata matches the ImageWriter layout')
