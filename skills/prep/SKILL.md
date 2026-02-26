---
name: prep
description: Prepare an original file for AgentMark annotation by creating an .eaml working copy with escaped collision tokens. Can only be activated by user explicitly running the /prep command.
---

# Prep Skill

The `prep` skill takes an original file and creates a `.eaml` working copy ready for annotation. It adds YAML frontmatter and escapes all characters that collide with AgentMark syntax (sigil and delimiter tokens).

## Usage

```
/prep <filename>
```

Optional arguments:
- `--sigil <char>` — custom sigil character (default: `@`)
- `--delimiter <pair>` — custom delimiter pair (default: `<>`)

## Workflow

Run the prep script:

```
python v2/skills/prep/scripts/prep.py <filename> [--sigil <char>] [--delimiter <pair>]
```

The script:
1. Reads the original file
2. Escapes all occurrences of the sigil and delimiter characters in the content
3. Writes `<filename>.eaml` with YAML frontmatter and escaped content
4. Prints the output path to stdout

Report the output path to the user.
