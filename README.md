# EAML — Extensible Agentic Markup Language

**Inline annotations that drive agentic writing workflows.**

EAML lets you embed annotations directly inside your Markdown, LaTeX, or other text files to tell an AI agent (e.g., Claude Code) *exactly* what to rewrite, expand, fact-check, cite, or any your customized agentic workflow — right next to the text it should act on.

```
                    your document
                    ┌─────────────────────────────────────────────┐
                    │ ...regular text...                          │
                    │                                             │
                    │ @text to edit@<prompt rewrite for clarity>  │
                    │                                             │
                    │ ...more text...                             │
                    └─────────────────────────────────────────────┘
                                        │
                              /execute file.eaml
                              (in your AI agent chat window)
                                        │
                                        ▼
                    ┌─────────────────────────────────────────────┐
                    │ ...regular text...                          │
                    │                                             │
                    │ rewritten, clearer text                     │
                    │                                             │
                    │ ...more text...                             │
                    └─────────────────────────────────────────────┘
```

---

## Quick start

> **Prerequisites:** An AI coding agent that supports [Agent Skills](https://agentskills.io/home) (e.g. Claude Code, Codex, Cursor).

**1. Install the skills**

Simpy copy the `skills/` folder into your agent's skills directory. For example, in Claude Code:

```
.claude/
  skills/
    execute/
    prompt/
    verify/
    cite/
    ...
```

**2. Create an annotated file**

Write your document as usual, then add EAML annotations where you want AI help. You can either save it with an `.eaml` extension (e.g. `notes.md.eaml`) or edit the native file directly (e.g. `notes.md`).

**Minimal example**

```text
---
target: notes.md
description: Personal research notes; keep the tone concise and technical.
sigil: "@"
delimiter: "<>"
---

<context style>
- Prefer short sentences.
- Keep terminology consistent.
</context style>

@Transformers are strong baselines for sequence modeling, but they can be
compute-heavy at long context lengths.@<param context:style output:replace><prompt Rewrite for clarity in 2 sentences. Preserve any numbers or equations.>
```

**3. Run it**

In your agent's chat interface, type:

```
/execute notes.md.eaml
```

The agent processes every annotation top-to-bottom and writes results back into the same file.

**Optional helper commands:**

| Command | What it does |
|---|---|
| `/prep <file>` | Creates `<file>.eaml` from an existing file, escaping any characters that conflict with EAML syntax. |
| `/render <file>.eaml` | Produces a clean output file with all annotations stripped. |

---


**Reading the exampple annotation:**

| Part | Meaning |
|---|---|
| `@...@` | The only text the agent is allowed to edit. |
| `<param context:style output:replace>` | Attach the `style` context block; replace the scoped text with the result. |
| `<prompt ...>` | Call `prompt` skill ("who to process this"), with instructions ("what to do"). |


After you run `/execute`, the runtime may also insert `<output ...>` (the result) and `<hash ...>` (a fingerprint for skipping unchanged work on re-runs). You don't write these by hand.

---

## Why EAML

Today's AI writing tools force you into one of two awkward workflows: either you paste text into a chatbot and copy results back, or you hand an agent your entire document and hope it doesn't break what you didn't want changed.

EAML fixes this. You mark *exactly* what you want help with, *right where it lives*, and the agent only touches those spans.

- **No copy-paste loops** — annotations live next to the text they affect. You stay in your editor; the agent comes to you.
- **Surgical precision** — `@...@` scopes lock down what the agent can edit. Everything outside is untouched. `<<...>>` protects specific numbers, quotes, or citations even inside an editable span.
- **Context without noise** — `<context ...>` blocks feed the agent only the background it needs, not your whole document. Less noise means better output.
- **One file, many tasks** — each annotation runs in isolation with its own thread, so a rewrite request in paragraph 2 never interferes with a fact-check in paragraph 10.
- **Incremental runs** — change one annotation and re-run; unchanged ones are skipped automatically via `<hash>`. No wasted tokens, no redundant rewrites.
- **Extensible via Agent Skills** — each workflow is a plain `SKILL.md` file following the [Agent Skills](https://agentskills.io/home) framework. Write your own skill to handle any custom request — no plugin API, no core language changes.
- **Installation free** — just copy the skills folder into your agent's skills directory. No packages, no build steps, no dependencies.
- **Native Agentic** — works with any agent that supports skill feature (Claude Code, Codex, Cursor, and more). 

---

## Syntax at a glance

### Full directive (scoped edit)

```text
@editable text@<prompt improve wording>
```

Only the text inside `@...@` is editable.

### Inline directive (act near here)

```text
This paragraph needs a reference. <cite APA>
```

No `@...@` span — the runtime uses the surrounding paragraph as context.

### Context blocks (reusable background)

Define a named block once:

```text
<context objectives>
1. Make the intro accessible.
2. Keep technical accuracy.
</context objectives>
```

Then attach it to any request via `<param>`:

```text
@text@<param context:objectives><prompt expand this>
```

### Protected spans (never edit)

```text
Our method improved accuracy by <<3.2%>>. <prompt proofread>
```

Text inside `<<...>>` is preserved exactly, even when the surrounding text is rewritten.

### Escapes

Use backslash for literal reserved characters:

- `\@` → literal `@`
- `\<` → literal `<`
- `\>` → literal `>`

---

## Directive fields reference

| Field | Purpose |
|---|---|
| `@...@` | Editable scope for a full directive. |
| `<<...>>` | Protected region; must not be altered. |
| `<param ...>` | Execution settings (context, output mode, source). |
| `<skillname ...>` | A request that dispatches to a skill (e.g. `<prompt ...>`, `<verify ...>`, `<cite ...>`). |
| `<output ...>` | Result written by the runtime; also serves as local history for later requests. |
| `<hash ...>` | Fingerprint used to skip unchanged annotations on re-run. |

**Common `<param>` keys:**

| Key | Example | Meaning |
|---|---|---|
| `context:` | `context:style;objectives` | Attach named context blocks. |
| `output:` | `output:append`, `output:replace`, `output:file` | Control how results are written back. |
| `source:` | `source:refs.bib`, `source:web` | Where research-oriented skills should look (`web`, `arxiv`, `local`, or a file path). |

---

## Built-in skills

| Skill | What it does |
|---|---|
| `prompt` | Rewrite, expand, summarize, or generate text. |
| `verify` | Fact-check claims (returns a verdict + references). |
| `cite` | Find and format a citation (citation string or BibTeX). |
| `placeholder` / `ph` | Inline-only filler for "TODO"-style slots. |
| `plan` | Produce a revision plan instead of changing text. |
| `resolve` | Finalize a prior output (accept / discard / integrate). |

---

## What `/execute` does

1. **Parse** — finds every annotation in the file, top to bottom.
2. **Build tasks** — for each annotation, assembles the editable content (or inline neighborhood), relevant `<context>` blocks, the request (`<prompt>`, `<verify>`, etc.), and any prior `<output>` history.
3. **Run skill** — dispatches to the matching skill in isolation.
4. **Write back** — applies results according to the `output:` param (`replace` rewrites the `@...@` span; `append` keeps the original and attaches an `<output>` block).
5. **Update hash** — stamps `<hash ...>` so unchanged annotations are skipped on the next run.

---

## Custom tokens

If `@`, `<>`, or `<<>>` conflict with your document syntax, override them in frontmatter, e.g.:

```yaml
---
target: article.tex
sigil: "%"
delimiter: "{}"     # exactly 2 chars: open + close
protect: "[[]]"     # open "[[" and close "]]"
---
```

---

## Writing your own skill

1. Create `v2/skills/<skillname>/SKILL.md` with YAML frontmatter (`name`, `description`).
2. Define how the skill reads the standard extraction fields (`Original File`, `Content to Modify`, `Parameters`, `Context`, `Request`, `Output`, `Hash`).
3. Define the skill's workflow
4. Return plain text (or a documented format). Do not write files — `/execute` handles write-back.


---

## Repo layout

```
EAML/
├── README.md
├── examples/
└── skills/
    ├── execute/
    ├── prompt/
    ├── verify/
    ├── cite/
    ├── placeholder/
    ├── plan/
    ├── resolve/
    ├── prep/
    ├── render/
    └── <your-custom-skill>/
```
