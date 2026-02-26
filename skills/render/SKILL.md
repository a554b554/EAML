---
name: render
description: Render an annotated EAML file into a clean document by removing all annotations and unescaping tokens.
---

# Render Skill

The `render` skill converts an annotated `.eaml` file back into a clean original document. It removes all AgentMark syntax (sigils, directives, context blocks, protected region markers) and unescapes collision tokens.

## Usage

```
/render <filename>
```

## Workflow

Run the render script:

```
python v2/skills/render/scripts/render.py <filename>
```

The script:
1. Reads the YAML frontmatter for `target`, `sigil`, `delimiter`, and `protect` settings
2. Falls back to defaults (`@`, `<>`, `<<>>`) if no frontmatter exists
3. Removes context blocks, full statement annotations, and inline directives
4. Strips protected region markers (keeps inner text)
5. Unescapes all collision tokens (`\@` → `@`, `\<` → `<`, `\>` → `>`)
6. Writes the clean document to `target` (or derives output name from input filename if no target specified)
7. Prints the output path to stdout

Report the output path to the user.
