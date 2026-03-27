#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

SKIP_DIRS = {
    '.git',
    '__pycache__',
    '.pytest_cache',
    'venv',
    'node_modules',
    'bot_data',
    'cardinal',
    '_tmp_playerok_universal',
    'Playerok Universal LATEST version',
}

CHECK_EXTENSIONS = {'.py', '.json', '.yml', '.yaml', '.toml', '.md', '.txt'}
SKIP_FILES = {'check_mojibake.py'}

KNOWN_BAD_SEQUENCES = (
    "Рџ",
    "РЎ",
    "Рќ",
    "С‚",
    "СЏ",
    "СЂ",
    "рџ",
    "вЂ",
    "в„",
    "вќ",
    "вљ",
    "гѓ",
    "Ð",
    "Ñ",
    "Â",
    "Ã",
    "�",
)


def _iter_files(root: Path):
    for path in root.rglob('*'):
        if not path.is_file():
            continue
        if path.name in SKIP_FILES:
            continue
        if path.suffix.lower() not in CHECK_EXTENSIONS:
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        yield path


def _line_is_suspicious(line: str) -> bool:
    stripped = line.strip()
    if not stripped or stripped.startswith('#'):
        return False
    if 'http://' in stripped or 'https://' in stripped:
        return False
    markers = sum(stripped.count(seq) for seq in KNOWN_BAD_SEQUENCES)
    return markers >= 2


def scan_tree(root: Path) -> list[tuple[Path, int, str]]:
    issues: list[tuple[Path, int, str]] = []
    for file_path in _iter_files(root):
        try:
            lines = file_path.read_text(encoding='utf-8', errors='ignore').splitlines()
        except Exception:
            continue
        for i, line in enumerate(lines, start=1):
            if _line_is_suspicious(line):
                issues.append((file_path, i, line.strip()))
    return issues


def _safe_print(text: str):
    try:
        print(text)
    except Exception:
        data = (text + '\n').encode('utf-8', errors='replace')
        sys.stdout.buffer.write(data)


def main() -> int:
    parser = argparse.ArgumentParser(description='Detect mojibake in project files.')
    parser.add_argument('--root', default='.', help='Root directory to scan.')
    parser.add_argument('--max-lines', type=int, default=80, help='How many issue lines to print.')
    args = parser.parse_args()

    root = Path(args.root).resolve()
    issues = scan_tree(root)

    if not issues:
        _safe_print('Mojibake check passed: no suspicious lines found.')
        return 0

    _safe_print(f'Mojibake check failed: {len(issues)} suspicious lines found.')
    for file_path, line_no, line in issues[: args.max_lines]:
        _safe_print(f'- {file_path}:{line_no}: {line[:200]}')
    if len(issues) > args.max_lines:
        _safe_print(f'... and {len(issues) - args.max_lines} more lines')
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
