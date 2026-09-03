# `install-skills`

Expose every MSXDAW skill in a project's `.cursor/skills/` directory and remove
workbench links made stale by a rename or deletion.

## When to use it

Run this after pulling a workbench revision that adds, renames, or removes
skills; after moving a game checkout; or when project skill links are missing.
`add-skill` and `scaffold` already run it.

## Prerequisites

- Bash, Python 3, and standard symlink utilities (`ln` and `readlink`).
- Write permission for the destination directory.
- Run the helper from the workbench whose `skills/` directories should be
  linked.

## Syntax

```sh
tools/workbench/bin/install-skills
```

There are no command-line arguments or options. The script does not parse its
arguments, so accidental extra arguments are ignored.

By default, the destination is selected in this order:

1. Walk upward from the current directory to the nearest `workbench.cfg` and
   use `<game-root>/.cursor/skills`.
2. When this helper is vendored at `<game-root>/tools/workbench`, use that game
   root even if the command was launched outside it.
3. In a standalone MSXDAW checkout with no game root, use
   `<workbench-root>/.cursor/skills`.

Set `CURSOR_SKILLS` to use a different project-local destination:

```sh
CURSOR_SKILLS="$PWD/.cursor/skills" tools/workbench/bin/install-skills
```

An empty `CURSOR_SKILLS` value is the same as leaving it unset. The destination
must not resolve to the user-global `~/.cursor/skills`.

## Examples

Refresh links after updating the submodule:

```sh
git submodule update --init
tools/workbench/bin/install-skills
```

Install from a standalone workbench into an explicit game checkout:

```sh
CURSOR_SKILLS=/work/msx-cart/.cursor/skills ./bin/install-skills
```

## Outputs and effects

For each immediate directory under `tools/workbench/skills/`, the helper
creates or replaces a relative symlink with the same name under the
destination. Existing paths at those names are affected as follows:

- A symlink is retargeted to the current workbench skill.
- A regular file is replaced by the symlink.
- A real directory causes `ln` to fail; it is not deleted.

The helper then removes destination symlinks that point into this workbench's
skill tree but whose matching source skill no longer exists. It leaves regular
files, directories, and unrelated symlinks alone.

It also removes old symlinks in `~/.cursor/skills` when they point into this
workbench's skills. This migration cleanup is the only intended effect on the
user-global directory; new links are never installed there.

Typical output is:

```text
unlinked stale old-skill
linked 13 skill(s) -> /work/msx-cart/.cursor/skills
```

The count is the number of current source skill directories, not the number of
links that changed.

## Errors and gotchas

- `install-skills: refusing ~/.cursor/skills (user-global)` means the selected
  destination is the forbidden global directory. Point `CURSOR_SKILLS` at a
  project-local `.cursor/skills` directory.
- An existing regular file with the same name as a workbench skill is replaced.
  Preserve or rename such a file before running the helper. A real directory
  blocks installation and must be moved or renamed before retrying.
- Destination selection follows the current working directory before the
  vendored-workbench fallback. When working inside nested game trees, confirm
  the final `linked ... -> DEST` line.
- Stale cleanup recognizes links into layouts named `tools/workbench/skills`
  or `msxdaw/skills`, plus absolute links into the current checkout. Unrelated
  broken links are preserved.
- The helper does not copy skill contents, change source skills, add files to
  Git, or commit anything.

## Related helpers and skills

- [`add-skill`](add-skill.md) creates a reusable skill skeleton and then calls
  this helper.
- [`scaffold`](scaffold.md) installs workbench skills into a newly created game
  repository.
- `tools/workbench/AGENTS.md` describes the boundary between reusable
  workbench skills and cart-specific `.agents/skills/`.
