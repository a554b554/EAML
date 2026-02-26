"""Render an annotated EAML file into a clean document.

Removes all AgentMark annotations, strips protected region markers,
and unescapes collision tokens.
"""

import sys
import os
import re
import yaml


def parse_frontmatter(text):
    """Extract YAML frontmatter and return (config_dict, remaining_text)."""
    if not text.startswith("---"):
        return {}, text
    end = text.find("---", 3)
    if end == -1:
        return {}, text
    yaml_block = text[3:end].strip()
    # Quote bare special chars that YAML can't handle
    lines = []
    for line in yaml_block.split('\n'):
        if ':' in line:
            key, _, val = line.partition(':')
            val = val.strip()
            if val and not val.startswith('"') and not val.startswith("'"):
                if val in ('@', '<>', '<<>>') or '@' in val:
                    val = f'"{val}"'
                    line = f'{key}: {val}'
        lines.append(line)
    yaml_block = '\n'.join(lines)
    config = yaml.safe_load(yaml_block) or {}
    rest = text[end + 3:]
    if rest.startswith("\n"):
        rest = rest[1:]
    return config, rest


def remove_context_blocks(text, open_delim, close_delim):
    """Remove context blocks and collapse extra blank lines."""
    od = re.escape(open_delim)
    cd = re.escape(close_delim)
    pattern = re.compile(
        od + r'context\s+(\S+)' + cd
        + r'.*?'
        + od + r'/context\s+\1' + cd,
        re.DOTALL
    )
    text = pattern.sub('', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text


def strip_full_statements(text, sigil, open_delim, close_delim):
    """Replace @content@<directives...> with just content."""
    result = []
    i = 0
    n = len(text)
    delims = open_delim + close_delim
    while i < n:
        if text[i] == '\\' and i + 1 < n and text[i + 1] == sigil:
            result.append('\\')
            result.append(sigil)
            i += 2
            continue
        if text[i] == '\\' and i + 1 < n and text[i + 1] in delims:
            result.append('\\')
            result.append(text[i + 1])
            i += 2
            continue
        if text[i] == sigil:
            # Found opening sigil - look for closing sigil
            j = i + 1
            content = []
            found_close = False
            while j < n:
                if text[j] == '\\' and j + 1 < n and text[j + 1] == sigil:
                    content.append('\\')
                    content.append(sigil)
                    j += 2
                    continue
                if text[j] == sigil:
                    # Found closing sigil - consume all trailing directives
                    k = j + 1
                    while k < n and text[k] == open_delim:
                        m = k + 1
                        depth = 1
                        while m < n and depth > 0:
                            if text[m] == '\\' and m + 1 < n and text[m + 1] in delims:
                                m += 2
                                continue
                            if text[m] == open_delim:
                                depth += 1
                            elif text[m] == close_delim:
                                depth -= 1
                            m += 1
                        k = m
                    result.append(''.join(content))
                    i = k
                    found_close = True
                    break
                content.append(text[j])
                j += 1
            if not found_close:
                result.append(text[i])
                i += 1
        else:
            result.append(text[i])
            i += 1
    return ''.join(result)


def strip_inline_directives(text, open_delim, close_delim):
    """Remove inline directive tags."""
    result = []
    i = 0
    n = len(text)
    delims = open_delim + close_delim
    while i < n:
        if text[i] == '\\' and i + 1 < n and text[i + 1] in delims:
            result.append('\\')
            result.append(text[i + 1])
            i += 2
            continue
        if text[i] == open_delim:
            # Check if this is a protected region
            if i + 1 < n and text[i + 1] == open_delim:
                result.append(open_delim + open_delim)
                i += 2
                continue
            # Check if this looks like a directive: <word ...>
            j = i + 1
            tag_start = j
            while j < n and text[j] not in (' ', '\t', '\n', close_delim):
                if text[j] == '\\' and j + 1 < n and text[j + 1] in delims:
                    j += 2
                    continue
                j += 1
            tag_type = text[tag_start:j].strip()
            if tag_type and tag_type.isalpha():
                # Find closing delimiter
                k = j
                depth = 1
                while k < n and depth > 0:
                    if text[k] == '\\' and k + 1 < n and text[k + 1] in delims:
                        k += 2
                        continue
                    if text[k] == open_delim:
                        depth += 1
                    elif text[k] == close_delim:
                        depth -= 1
                    k += 1
                if depth == 0:
                    # Remove directive and trailing space before it
                    while result and result[-1] == ' ':
                        result.pop()
                    i = k
                    continue
            result.append(text[i])
            i += 1
        else:
            result.append(text[i])
            i += 1
    return ''.join(result)


def strip_protected(text, protect_open, protect_close):
    """Replace <<text>> with text (keep inner content, remove markers)."""
    result = []
    i = 0
    n = len(text)
    lo = len(protect_open)
    lc = len(protect_close)
    while i < n:
        if text[i:i + lo] == protect_open:
            j = i + lo
            end = text.find(protect_close, j)
            if end != -1:
                result.append(text[j:end])
                i = end + lc
            else:
                result.append(text[i])
                i += 1
        else:
            result.append(text[i])
            i += 1
    return ''.join(result)


def unescape(text, sigil, open_delim, close_delim):
    """Unescape collision tokens back to their original characters."""
    text = text.replace('\\' + sigil, sigil)
    if open_delim != sigil:
        text = text.replace('\\' + open_delim, open_delim)
    if close_delim != sigil and close_delim != open_delim:
        text = text.replace('\\' + close_delim, close_delim)
    return text


def main():
    if len(sys.argv) < 2:
        print("Usage: python render.py <filename>", file=sys.stderr)
        sys.exit(1)

    filepath = sys.argv[1]
    with open(filepath, 'r', encoding='utf-8') as f:
        text = f.read()

    config, body = parse_frontmatter(text)
    sigil = config.get('sigil', '@')
    delimiter = config.get('delimiter', '<>')
    protect = config.get('protect', '<<>>')
    open_delim = delimiter[0]
    close_delim = delimiter[1]
    protect_open = protect[:len(protect) // 2]
    protect_close = protect[len(protect) // 2:]

    # Determine output path
    target = config.get('target')
    if target:
        input_dir = os.path.dirname(os.path.abspath(filepath))
        output_path = os.path.join(input_dir, target)
    else:
        # No target specified — render in place
        output_path = filepath

    # Step 1: Remove context blocks
    body = remove_context_blocks(body, open_delim, close_delim)

    # Step 2: Strip full statements (keep content, remove sigils + directives)
    body = strip_full_statements(body, sigil, open_delim, close_delim)

    # Step 3: Strip inline directives
    body = strip_inline_directives(body, open_delim, close_delim)

    # Step 4: Strip protected region markers
    body = strip_protected(body, protect_open, protect_close)

    # Step 5: Unescape collision tokens
    body = unescape(body, sigil, open_delim, close_delim)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(body)

    print(output_path)


if __name__ == '__main__':
    main()
