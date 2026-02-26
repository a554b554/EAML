"""Strip AgentMark annotations from a file to produce a clean document."""

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
    # Quote bare special chars that YAML can't handle (like @)
    lines = []
    for line in yaml_block.split('\n'):
        if ':' in line:
            key, _, val = line.partition(':')
            val = val.strip()
            # If value is a bare special char, quote it
            if val and not val.startswith('"') and not val.startswith("'"):
                if val in ('@', '<>', '<<>>') or any(c in val for c in '@'):
                    val = f'"{val}"'
                    line = f'{key}: {val}'
        lines.append(line)
    yaml_block = '\n'.join(lines)
    config = yaml.safe_load(yaml_block) or {}
    # Skip past the closing --- and any immediate newline
    rest = text[end + 3:]
    if rest.startswith("\n"):
        rest = rest[1:]
    return config, rest


def remove_context_blocks(text, delim_open, delim_close):
    """Remove <context name>...</context name> blocks and collapse extra blank lines."""
    pattern = re.compile(
        re.escape(delim_open) + r'context\s+(\S+)' + re.escape(delim_close)
        + r'.*?'
        + re.escape(delim_open) + r'/context\s+\1' + re.escape(delim_close),
        re.DOTALL
    )
    text = pattern.sub('', text)
    # Collapse runs of 3+ newlines to 2
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text


def strip_full_statements(text, sigil):
    """Replace @content@<directives...> with just content."""
    result = []
    i = 0
    n = len(text)
    while i < n:
        # Check for escaped sigil
        if text[i] == '\\' and i + 1 < n and text[i + 1] == sigil:
            result.append('\\')
            result.append(sigil)
            i += 2
            continue
        if text[i] == '\\' and i + 1 < n and text[i + 1] in '<>':
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
                    # Found closing sigil - now consume all trailing directives
                    k = j + 1
                    # Consume directive tags <...>
                    while k < n:
                        # Skip whitespace between directives? No, directives are adjacent
                        if text[k] == '<':
                            # Find matching >
                            m = k + 1
                            depth = 1
                            while m < n and depth > 0:
                                if text[m] == '\\' and m + 1 < n and text[m + 1] in '<>':
                                    m += 2
                                    continue
                                if text[m] == '<':
                                    # Check for protected region <<
                                    depth += 1
                                elif text[m] == '>':
                                    depth -= 1
                                m += 1
                            k = m
                        else:
                            break
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


def strip_inline_directives(text, delim_open, delim_close):
    """Remove inline directive tags <type value>."""
    result = []
    i = 0
    n = len(text)
    while i < n:
        if text[i] == '\\' and i + 1 < n and text[i + 1] in '<>':
            result.append('\\')
            result.append(text[i + 1])
            i += 2
            continue
        if text[i] == '<':
            # Check if this is a protected region <<
            if i + 1 < n and text[i + 1] == '<':
                result.append('<<')
                i += 2
                continue
            # Check if this looks like a directive <word ...>
            j = i + 1
            # Try to read the tag type
            tag_start = j
            while j < n and text[j] not in ' \t\n>':
                if text[j] == '\\' and j + 1 < n and text[j + 1] in '<>':
                    j += 2
                    continue
                j += 1
            tag_type = text[tag_start:j].strip()
            # Known directive types or skill names
            if tag_type and tag_type.isalpha():
                # Find closing >
                k = j
                depth = 1
                while k < n and depth > 0:
                    if text[k] == '\\' and k + 1 < n and text[k + 1] in '<>':
                        k += 2
                        continue
                    if text[k] == '<':
                        depth += 1
                    elif text[k] == '>':
                        depth -= 1
                    k += 1
                if depth == 0:
                    # Remove directive and any leading whitespace before it
                    # Trim trailing space before directive
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
    """Replace <<text>> with text."""
    result = []
    i = 0
    n = len(text)
    po = protect_open
    pc = protect_close
    lo = len(po)
    lc = len(pc)
    while i < n:
        if text[i:i + lo] == po:
            # Find closing protect
            j = i + lo
            end = text.find(pc, j)
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


def unescape(text):
    """Unescape \\@ → @, \\< → <, \\> → >."""
    text = text.replace('\\@', '@')
    text = text.replace('\\<', '<')
    text = text.replace('\\>', '>')
    return text


def main():
    if len(sys.argv) < 2:
        print("Usage: python strip.py <filename>", file=sys.stderr)
        sys.exit(1)

    filepath = sys.argv[1]
    with open(filepath, 'r', encoding='utf-8') as f:
        text = f.read()

    config, body = parse_frontmatter(text)
    target = config.get('target')
    if not target:
        print("Error: no 'target' field in frontmatter", file=sys.stderr)
        sys.exit(1)
    sigil = config.get('sigil', '@')
    delim = config.get('delimiter', '<>')
    protect = config.get('protect', '<<>>')

    delim_open = delim[0]
    delim_close = delim[-1]
    protect_open = protect[:len(protect) // 2]
    protect_close = protect[len(protect) // 2:]

    # Step 1: Remove context blocks
    body = remove_context_blocks(body, delim_open, delim_close)

    # Step 2: Strip full statements
    body = strip_full_statements(body, sigil)

    # Step 3: Strip inline directives
    body = strip_inline_directives(body, delim_open, delim_close)

    # Step 4: Strip protected regions
    body = strip_protected(body, protect_open, protect_close)

    # Step 5: Unescape
    body = unescape(body)

    # Write to target
    input_dir = os.path.dirname(os.path.abspath(filepath))
    target_path = os.path.join(input_dir, target)
    with open(target_path, 'w', encoding='utf-8') as f:
        f.write(body)

    print(target_path)


if __name__ == '__main__':
    main()
