"""Parse AgentMark annotations and produce one .md extraction file per annotation."""

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


def extract_context_blocks(text, open_delim='<', close_delim='>'):
    """Extract <context name>...</context name> blocks.
    Returns (cleaned_text, contexts_dict).
    """
    contexts = {}
    od = re.escape(open_delim)
    cd = re.escape(close_delim)
    pattern = re.compile(
        od + r'context\s+(\S+)' + cd + r'\n?(.*?)\n?' + od + r'/context\s+\1' + cd,
        re.DOTALL
    )
    for m in pattern.finditer(text):
        name = m.group(1)
        content = m.group(2).strip()
        contexts[name] = content
    cleaned = pattern.sub('', text)
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
    return cleaned, contexts


def find_directive_end(text, start, open_delim='<', close_delim='>'):
    """Find the end of a directive tag starting at position start.
    Returns the index after the closing delimiter, or -1 if not found.
    Handles escaped delimiters and nested protected regions.
    """
    i = start + 1  # skip opening delimiter
    depth = 1
    n = len(text)
    delims = open_delim + close_delim
    while i < n and depth > 0:
        if text[i] == '\\' and i + 1 < n and text[i + 1] in delims:
            i += 2
            continue
        if text[i] == open_delim:
            depth += 1
        elif text[i] == close_delim:
            depth -= 1
        i += 1
    return i if depth == 0 else -1


def parse_directive(tag_content):
    """Parse the content of a directive tag (without < >).
    Returns (type, value) tuple.
    """
    tag_content = tag_content.strip()
    # Split on first space
    parts = tag_content.split(None, 1)
    dtype = parts[0] if parts else tag_content
    value = parts[1] if len(parts) > 1 else ''
    return dtype, value


def parse_params(value):
    """Parse param value like 'context:objectives;budget output:append mode:replace'.
    Returns dict of key -> value_string.
    """
    params = {}
    for token in value.split():
        if ':' in token:
            k, v = token.split(':', 1)
            if k in params:
                # Merge with semicolon for multiple param tags with same key
                params[k] = params[k] + ';' + v
            else:
                params[k] = v
        else:
            params[token] = ''
    return params


def extract_full_statements(text, sigil, open_delim='<', close_delim='>'):
    """Find all full statements @content@<directives...>.
    Returns list of dicts with keys: content, directives, start, end.
    """
    statements = []
    i = 0
    n = len(text)
    while i < n:
        # Check for escaped sigil
        if text[i] == '\\' and i + 1 < n and text[i + 1] == sigil:
            i += 2
            continue
        if text[i] == sigil:
            # Found opening sigil - find closing sigil
            stmt_start = i
            j = i + 1
            content_chars = []
            found_close = False
            while j < n:
                if text[j] == '\\' and j + 1 < n and text[j + 1] == sigil:
                    content_chars.append('\\')
                    content_chars.append(sigil)
                    j += 2
                    continue
                if text[j] == sigil:
                    # Found closing sigil - now collect directives
                    content = ''.join(content_chars)
                    directives = []
                    k = j + 1
                    while k < n and text[k] == open_delim:
                        end = find_directive_end(text, k, open_delim, close_delim)
                        if end == -1:
                            break
                        tag_inner = text[k + 1:end - 1]
                        directives.append(tag_inner)
                        k = end
                    statements.append({
                        'content': content,
                        'directives': directives,
                        'start': stmt_start,
                        'end': k,
                    })
                    i = k
                    found_close = True
                    break
                content_chars.append(text[j])
                j += 1
            if not found_close:
                i += 1
        else:
            i += 1
    return statements


def get_surrounding_paragraph(text, pos):
    """Extract the paragraph (block of text separated by blank lines) around pos."""
    # Find paragraph start: search backward for a blank line (two consecutive newlines)
    para_start = 0
    search_back = text.rfind('\n\n', 0, pos)
    if search_back != -1:
        para_start = search_back + 2

    # Find paragraph end: search forward for a blank line
    search_fwd = text.find('\n\n', pos)
    if search_fwd != -1:
        para_end = search_fwd
    else:
        para_end = len(text)

    return text[para_start:para_end].strip()


def get_inline_context(text, dir_start, dir_end):
    """Build content for an inline directive with surrounding paragraphs.

    Returns a string containing:
      - the paragraph before (if any)
      - the current paragraph with @@ replacing the directive tags
      - the paragraph after (if any)

    Paragraphs are separated by blank lines.
    """
    # Current paragraph boundaries
    cur_start = 0
    search_back = text.rfind('\n\n', 0, dir_start)
    if search_back != -1:
        cur_start = search_back + 2

    search_fwd = text.find('\n\n', dir_end)
    cur_end = search_fwd if search_fwd != -1 else len(text)

    # Current paragraph with @@ marker where the directive was
    current_para = (text[cur_start:dir_start] + '@@' + text[dir_end:cur_end]).strip()

    # Previous paragraph
    prev_para = ''
    if cur_start > 0:
        prev_end = cur_start - 2  # skip the \n\n separator
        prev_start = 0
        search_prev = text.rfind('\n\n', 0, prev_end)
        if search_prev != -1:
            prev_start = search_prev + 2
        prev_para = text[prev_start:prev_end + 2].strip()

    # Next paragraph
    next_para = ''
    if search_fwd is not None and search_fwd != -1:
        next_start = search_fwd + 2
        next_end_search = text.find('\n\n', next_start)
        next_end = next_end_search if next_end_search != -1 else len(text)
        next_para = text[next_start:next_end].strip()

    parts = []
    if prev_para:
        parts.append(prev_para)
    parts.append(current_para)
    if next_para:
        parts.append(next_para)

    return '\n\n'.join(parts)


def extract_inline_directives(text, sigil, full_statement_ranges,
                              open_delim='<', close_delim='>'):
    """Find inline directives - directive tags not inside full statements.
    Returns list of dicts with keys: directives, start, end, paragraph.
    """
    inlines = []
    i = 0
    n = len(text)
    delims = open_delim + close_delim

    def in_full_statement(pos):
        for r in full_statement_ranges:
            if r[0] <= pos < r[1]:
                return True
        return False

    while i < n:
        if text[i] == '\\' and i + 1 < n and text[i + 1] in delims:
            i += 2
            continue
        if text[i] == open_delim and not in_full_statement(i):
            # Check it's not a protected region or context block
            if i + 1 < n and text[i + 1] == open_delim:
                # Skip entire <<...>> protected region
                j = i + 2
                while j < n - 1:
                    if text[j] == close_delim and text[j + 1] == close_delim:
                        j += 2
                        break
                    j += 1
                else:
                    j = n
                i = j
                continue
            # Check if this looks like a directive: <word ...>
            j = i + 1
            while j < n and text[j] in ' \t':
                j += 1
            word_start = j
            while j < n and text[j] not in (' ', '\t', '\n', close_delim):
                j += 1
            word = text[word_start:j]
            if word and word.isalpha() and word not in ('context',):
                # Collect consecutive directive tags
                group_start = i
                directives = []
                k = i
                while k < n and text[k] == open_delim:
                    if k + 1 < n and text[k + 1] == open_delim:
                        break
                    end = find_directive_end(text, k, open_delim, close_delim)
                    if end == -1:
                        break
                    tag_inner = text[k + 1:end - 1]
                    dtype, _ = parse_directive(tag_inner)
                    if dtype == 'context':
                        break
                    directives.append(tag_inner)
                    k = end
                if directives:
                    # Build content with prev paragraph, current paragraph
                    # (with @@ marking directive position), and next paragraph
                    content = get_inline_context(text, group_start, k)
                    inlines.append({
                        'directives': directives,
                        'start': group_start,
                        'end': k,
                        'content': content,
                    })
                    i = k
                    continue
        i += 1
    return inlines


def resolve_contexts(params, contexts_dict):
    """Resolve context references from params.
    Returns list of (name, content_or_empty, resolved_bool).
    """
    results = []
    context_str = params.get('context', '')
    if not context_str:
        return results
    refs = context_str.split(';')
    for ref in refs:
        ref = ref.strip()
        if not ref:
            continue
        if ref in contexts_dict:
            results.append((ref, contexts_dict[ref], True))
        else:
            results.append((ref, '', False))
    return results


SKILL_ALIASES = {
    'ph': 'placeholder',
}


def build_extraction(annotation, index, source, contexts_dict):
    """Build extraction .md content for an annotation.

    Directives are dumped in document order. When multiple request/output
    pairs exist (conversation history), they are all included sequentially.
    The skill used for dispatch is determined by the *last* request directive
    (ignoring hash).
    """
    lines = []
    lines.append('# Original File')
    lines.append(source)
    lines.append('')

    # Content to Modify
    content = annotation.get('content', '')
    lines.append('# Content to Modify')
    lines.append(content)
    lines.append('')

    # First pass: collect params and context (order-independent)
    all_params = {}
    existing_hash = None

    for d in annotation['directives']:
        dtype, value = parse_directive(d)
        if dtype == 'param':
            p = parse_params(value)
            for k, v in p.items():
                if k in all_params:
                    all_params[k] = all_params[k] + ';' + v
                else:
                    all_params[k] = v
        elif dtype == 'hash':
            existing_hash = value.strip()

    # Parameters
    lines.append('# Parameters')
    if all_params:
        param_parts = [f'{k}:{v}' if v else k for k, v in all_params.items()]
        lines.append(' '.join(param_parts))
    else:
        lines.append('(none)')
    lines.append('')

    # Context
    lines.append('# Context')
    ctx_refs = resolve_contexts(all_params, contexts_dict)
    if ctx_refs:
        for name, content, resolved in ctx_refs:
            lines.append(f'## {name}')
            if resolved:
                lines.append(content)
            else:
                lines.append(f'(unresolved — agent should resolve this reference)')
            lines.append('')
    else:
        lines.append('(none)')
        lines.append('')

    # Second pass: dump request/output pairs in document order
    # This preserves conversation history for skills that need it.
    last_skill_name = None
    for d in annotation['directives']:
        dtype, value = parse_directive(d)
        if dtype in ('param', 'hash'):
            continue
        elif dtype == 'output':
            lines.append('# Output')
            lines.append(value)
            lines.append('')
        else:
            # Skill request directive
            dtype = SKILL_ALIASES.get(dtype, dtype)
            last_skill_name = dtype
            lines.append(f'# Request ({dtype})')
            lines.append(value)
            lines.append('')

    # Hash (always last)
    if existing_hash:
        lines.append('# Hash')
        lines.append(existing_hash)
        lines.append('')

    return '\n'.join(lines), last_skill_name, existing_hash


def main():
    if len(sys.argv) < 2:
        print("Usage: python parse.py <filename>", file=sys.stderr)
        sys.exit(1)

    filepath = sys.argv[1]
    with open(filepath, 'r', encoding='utf-8') as f:
        text = f.read()

    config, body = parse_frontmatter(text)
    sigil = config.get('sigil', '@')
    delimiter = config.get('delimiter', '<>')
    open_delim = delimiter[0]
    close_delim = delimiter[1]

    # Extract context blocks
    body_clean, contexts = extract_context_blocks(body, open_delim, close_delim)

    # Find full statements
    full_stmts = extract_full_statements(body_clean, sigil, open_delim, close_delim)

    # Find inline directives
    full_ranges = [(s['start'], s['end']) for s in full_stmts]
    inline_dirs = extract_inline_directives(body_clean, sigil, full_ranges,
                                            open_delim, close_delim)

    # Combine all annotations in document order
    annotations = []
    for s in full_stmts:
        annotations.append({
            'type': 'full',
            'content': s['content'],
            'directives': s['directives'],
            'start': s['start'],
        })
    for d in inline_dirs:
        annotations.append({
            'type': 'inline',
            'content': d.get('content', ''),
            'directives': d['directives'],
            'start': d['start'],
        })
    annotations.sort(key=lambda a: a['start'])

    # Create tmp directory
    input_dir = os.path.dirname(os.path.abspath(filepath))
    tmp_dir = os.path.join(input_dir, 'tmp')
    os.makedirs(tmp_dir, exist_ok=True)

    # Process each annotation
    summary_lines = []
    for idx, ann in enumerate(annotations):
        md_content, skill, existing_hash = build_extraction(ann, idx, filepath, contexts)
        filename = f'annotation_{idx}.md'
        md_path = os.path.join(tmp_dir, filename)
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(md_content)

        # Determine hash status
        if existing_hash:
            hash_status = 'stale'  # has hash but we can't verify without hash.py
        else:
            hash_status = 'new'

        skill_name = skill or 'unknown'
        summary_lines.append(f'{idx} {filename} {skill_name} {hash_status}')

    # Print summary
    for line in summary_lines:
        print(line)


if __name__ == '__main__':
    main()
