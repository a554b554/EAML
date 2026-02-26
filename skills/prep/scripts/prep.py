"""Prepare an original file for AgentMark annotation.

Creates a .eaml working copy with YAML frontmatter and escaped collision tokens.
"""

import sys
import os
import argparse


def escape_content(text, sigil, delimiter):
    """Escape all sigil and delimiter characters in text."""
    open_delim = delimiter[0]
    close_delim = delimiter[1]

    # Escape sigil
    text = text.replace(sigil, '\\' + sigil)

    # Escape delimiters (avoid double-escaping if sigil == delimiter char)
    if open_delim != sigil:
        text = text.replace(open_delim, '\\' + open_delim)
    if close_delim != sigil and close_delim != open_delim:
        text = text.replace(close_delim, '\\' + close_delim)

    return text


def build_frontmatter(target, sigil, delimiter):
    """Build YAML frontmatter string."""
    lines = [
        '---',
        f'target: {target}',
        f'sigil: "{sigil}"',
        f'delimiter: "{delimiter}"',
        '---',
    ]
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description='Prepare a file for AgentMark annotation.')
    parser.add_argument('filename', help='The original file to prepare')
    parser.add_argument('--sigil', default='@', help='Sigil character (default: @)')
    parser.add_argument('--delimiter', default='<>', help='Delimiter pair (default: <>)')
    args = parser.parse_args()

    filepath = args.filename
    sigil = args.sigil
    delimiter = args.delimiter

    if len(delimiter) != 2:
        print('Error: delimiter must be exactly 2 characters (open + close)', file=sys.stderr)
        sys.exit(1)

    if not os.path.isfile(filepath):
        print(f'Error: file not found: {filepath}', file=sys.stderr)
        sys.exit(1)

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    target = os.path.basename(filepath)
    escaped = escape_content(content, sigil, delimiter)
    frontmatter = build_frontmatter(target, sigil, delimiter)

    output_path = filepath + '.eaml'
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(frontmatter + '\n' + escaped)

    print(output_path)


if __name__ == '__main__':
    main()
