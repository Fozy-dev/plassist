from __future__ import annotations

import argparse
from pathlib import Path

SKIP_DIRS = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    "venv",
    "node_modules",
    "logs",
}

CHECK_EXTENSIONS = {".py", ".json", ".yml", ".yaml", ".toml", ".md", ".txt", ".ini"}
SKIP_FILES = {"repair_mojibake.py", "check_mojibake.py", "text_normalizer.py"}

MOJIBAKE_MARKERS = (
    "рџ",
    "вЂ",
    "в„",
    "вќ",
    "вљ",
    "гѓ",
    "Р",
    "С",
    "Ð",
    "Ñ",
    "Â",
    "Ã",
    "�",
)

# Very common sequences for UTF-8 text decoded as cp1251/cp866 and saved back.
BAD_SEQUENCES = (
    "Рџ",
    "РЎ",
    "Рќ",
    "С‚",
    "СЏ",
    "СЂ",
    "рџ",
    "вЂ",
)


def _iter_files(root: Path):
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in CHECK_EXTENSIONS:
            continue
        if path.name in SKIP_FILES:
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        yield path


def _contains_suspicious(text: str) -> bool:
    if not text:
        return False
    score = sum(text.count(marker) for marker in MOJIBAKE_MARKERS)
    bad_seq = sum(text.count(seq) for seq in BAD_SEQUENCES)
    return score >= 6 or bad_seq >= 3


def _quality_score(text: str) -> int:
    cyrillic = sum(1 for ch in text if "\u0400" <= ch <= "\u04FF")
    ascii_letters = sum(1 for ch in text if "a" <= ch.lower() <= "z")
    digits = sum(1 for ch in text if ch.isdigit())
    bad = sum(text.count(marker) for marker in MOJIBAKE_MARKERS)
    bad_seq = sum(text.count(seq) for seq in BAD_SEQUENCES)
    replacement = text.count("�")
    return cyrillic * 4 + ascii_letters + digits - bad * 5 - bad_seq * 12 - replacement * 20


def _decode_variant(text: str, source_encoding: str) -> str | None:
    try:
        encoded = text.encode(source_encoding, errors="ignore")
        if not encoded:
            return None
        decoded = encoded.decode("utf-8", errors="ignore")
        if not decoded:
            return None
        # Guard: if too much content disappeared, skip this candidate.
        if len(decoded) < int(len(text) * 0.75):
            return None
        return decoded
    except Exception:
        return None


def _best_repair(text: str) -> str:
    best = text
    best_score = _quality_score(text)
    queue = [text]
    seen = {text}

    for _ in range(3):
        new_queue = []
        for current in queue:
            for enc in ("latin1", "cp1251", "cp866"):
                candidate = _decode_variant(current, enc)
                if not candidate or candidate in seen:
                    continue
                seen.add(candidate)
                new_queue.append(candidate)
                score = _quality_score(candidate)
                if score > best_score:
                    best = candidate
                    best_score = score
        if not new_queue:
            break
        queue = new_queue

    return best


def repair_file(path: Path, dry_run: bool = False) -> bool:
    try:
        original = path.read_text(encoding="utf-8", errors="strict")
    except UnicodeError:
        return False
    except Exception:
        return False

    if not _contains_suspicious(original):
        return False

    repaired = _best_repair(original)
    if repaired == original:
        return False
    if _quality_score(repaired) <= _quality_score(original):
        return False

    if not dry_run:
        path.write_text(repaired, encoding="utf-8", newline="\n")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Repair mojibake in text files.")
    parser.add_argument("--root", default=".", help="Project root")
    parser.add_argument("--dry-run", action="store_true", help="Only print files that would change")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    changed = []

    for path in _iter_files(root):
        if repair_file(path, dry_run=args.dry_run):
            changed.append(path)

    mode = "would repair" if args.dry_run else "repaired"
    print(f"{mode}: {len(changed)} file(s)")
    for item in changed:
        print(f" - {item}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
