---
name: execute
description: Execute AgentMark annotated files — parse annotations, run subagents, write results back.
---

# Execute Skill

The `execute` skill is the main entry point for processing AgentMark annotated files. It orchestrates the full pipeline: parsing annotations into extraction files, checking hashes, dispatching subagents, and writing results back.

## Usage

```
/execute <filename>
```

## Workflow

### 1. Parse

Run `parse.py <filename>` to extract all annotations into individual `.md` files in a `tmp/` directory (sibling to the input file). The script prints a summary to stdout listing each annotation with its index, filename, skill, and hash status (`new`, `stale`, or `current`).

Note the parse should only execute once in a execute call, and the resulting `.md` files are used for all subsequent steps. Do not re-run the parse for each annotation.

### 2. Process Annotations Sequentially

For each annotation in order:

1. Read the extraction `.md` file (e.g., `tmp/annotation_0.md`).
2. Check if the annotation has a stored hash. If **no hash exists**, proceed directly to step 4. If a hash exists, run `hash.py <md_file>` to compute the current hash.
3. If the stored hash matches the computed hash, **skip** this annotation (it is up to date). Move to the next annotation. Otherwise, go to next step to re-execute.
4. Determine which skill to dispatch by finding the **last `# Request (skillname)`** in the extraction file (ignoring `# Hash`). This is the active request; any earlier `# Request` / `# Output` pairs are conversation history that provides context to the subagent.
   - Example: an annotation `<param xxx><prompt rewrite this><output improved text><verify check the facts>` produces an extraction with `# Request (prompt)` → `# Output` → `# Request (verify)`. Dispatch to the `verify` skill.
5. Spawn a subagent with the determined skill:
   - `# Request (prompt)` (last) → spawn subagent with the `prompt` skill
   - `# Request (verify)` (last) → spawn subagent with the `verify` skill
   - etc.
6. The subagent reads the `.md` file and returns its response.
7. Write the subagent's response back to the input file based on the output mode in `# Parameters` (default: `append` for full directives, `replace` for inline directives):
   - **replace**: Locate the annotation and replace the content between the `@...@` sigils with the response.
   - **append**: Insert `<output response>` after the last directive tag in the annotation (before `<hash>` if present).
   - **file**: Write the response to the path specified in `# Parameters`.
   - Sometimes the subagent will also return the response mode, you should use the following priority to determine the final output mode:
     1. The mode specified in `# Parameters` (if any)
     2. Inside the user's instruction in `# Request (skillname)` (e.g., `<prompt ..., and write reponse to xx.md>`)
     3. The mode specified in the subagent response (if any)
     4. Default to `append`
8. (Optional) You may optionally receive note from subagent how to handle the annotation after response (e.g., remove the annotation), just follow that instruction. If annotation is removed, no need to execute 9.
9. Compute the hash again (now including the output) and write `<hash computed_hash>` at the end of the annotation in the input file (overwrite the previous hash).
10. Clean up the temp `.md` file.

### 3. Report

After all annotations are processed, summarize what was executed and what was skipped.

## Scripts

| Script | Purpose |
|--------|---------|
| `scripts/parse.py` | Parse annotations → one `.md` extraction file per annotation, should only be executed  at the begining |
| `scripts/hash.py` | Compute 16-char hex SHA-256 hash for skip detection |
