# `add-skill`

Create the skeleton for a reusable MSXDAW agent skill and expose all workbench
skills to the current game project.

## When to use it

Use this helper when the guidance or workflow applies to more than one MSX
cart. Cart-specific addresses, source stems, RAM layouts, and dumpers belong in
the game repository's `.agents/skills/` instead.

## Prerequisites

- A Bash environment.
- A writable workbench `skills/` directory.
- The prerequisites of [`install-skills`](install-skills.md), which is always
  run before this helper exits.
- Run the copy of the helper in the workbench where the skill should live.

## Syntax

```sh
tools/workbench/bin/add-skill NAME
```

`NAME` is the one required positional argument and becomes both the directory
name under `tools/workbench/skills/` and the skill's frontmatter `name`.
There are no options and no default name. Quote a name if the shell would
otherwise split it, although lowercase hyphenated names such as
`msx-audio-trace` are the intended form.

The helper reads only the first positional argument. Extra arguments are
ignored, so do not rely on them as options.

## Example

From a game repository that vendors MSXDAW:

```sh
tools/workbench/bin/add-skill msx-audio-trace
```

This creates:

```text
tools/workbench/skills/msx-audio-trace/SKILL.md
```

The generated page contains valid frontmatter, a placeholder description, and
a reminder to keep the skill cart-neutral. Edit the `TODO` description and
replace the skeleton body with the engineer-facing workflow.

The helper then runs `tools/workbench/bin/install-skills`, which creates or
refreshes the project link:

```text
.cursor/skills/msx-audio-trace
  -> ../../tools/workbench/skills/msx-audio-trace
```

The exact relative link text depends on the project layout.

## Existing skills

If `tools/workbench/skills/NAME` already exists, the helper reports
`already exists: ...`, does not modify its `SKILL.md`, refreshes all workbench
skill links, and exits successfully.

## Errors and gotchas

- Omitting `NAME` prints `usage: add-skill <name>` and exits with status 2.
- The name is not validated. Slashes can create an unintended nested path, and
  whitespace or option-like names produce awkward skill directories. Use a
  simple lowercase hyphenated name.
- A failure from directory creation, file writing, or `install-skills` stops
  the command with a nonzero status. If the skeleton was created before link
  installation failed, fix the link-installation error and run
  `tools/workbench/bin/install-skills`.
- The generated skill is not complete until its placeholder is replaced.
- The helper does not add files to Git or create a commit.

## Related helpers and skills

- [`install-skills`](install-skills.md) refreshes links without creating a
  skill.
- `tools/workbench/AGENTS.md` defines whether a skill belongs in MSXDAW or in a
  game repository.
- `msx-scaffold` creates a new game repository and installs existing workbench
  skills.
