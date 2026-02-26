"""Compute a deterministic hash for an annotation extraction .md file."""

import sys
import hashlib
import re


def strip_hash_and_output(text):
    """Remove # Hash and # Output sections from extraction content."""
    lines = text.split('\n')
    result = []
    skip = False
    for line in lines:
        if line.startswith('# Hash'):
            skip = True
            continue
        elif line.startswith('# Output'):
            skip = True
            continue
        elif skip and line.startswith('# '):
            skip = False
        if not skip:
            result.append(line)
    return '\n'.join(result)


def compute_hash(text):
    """Compute SHA-256 hash and return first 16 hex chars."""
    h = hashlib.sha256(text.encode('utf-8')).hexdigest()
    return h[:16]


def main():
    if len(sys.argv) < 2:
        print("Usage: python hash.py <md_file>", file=sys.stderr)
        sys.exit(1)

    filepath = sys.argv[1]
    with open(filepath, 'r', encoding='utf-8') as f:
        text = f.read()

    cleaned = strip_hash_and_output(text)
    h = compute_hash(cleaned)
    print(h)


if __name__ == '__main__':
    main()
