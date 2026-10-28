# Codex installer troubleshooting

Use this guide for the Codex adapter in `codex/install.py`. The original Claude
installer is a separate workflow. Start with a dry-run. **Do not use Project
Antares or any valuable project as a recovery test fixture.**

## Quick non-mutating checks

Run from the skill-pack repository root:

```bash
python codex/install.py --help
python codex/install.py --scope user
python codex/install.py --scope project --project-root "/path/to/workspace"
```

A successful dry-run returns exit code 0 but **does not install** skills.
Look for target paths, existing roles, and overwrite warnings before approving
`--apply`. A blocked installation or recovery usually returns exit code 2.
A successful apply is not evidence Codex has discovered skills or connected
to Roblox Studio.

## Symptom and safe response

| Symptom | Meaning | What to do before retrying |
| --- | --- | --- |
| `Existing destination paths` / overwrite refusal | Skills or role files already exist | Review differences and backups. Only use `--force --apply` with explicit approval. |
| `existing Codex custom roles` | Existing TOML roles in user, CODEX_HOME, project, or ancestor scope could defeat sequential mode | Review and disable the roles **outside** the installer. Do not ignore the warning or assume built-in workers are disabled. |
| `Installer lock exists` | Another apply/recover operation may be active, or a prior operation stopped | Confirm the process is gone, inspect `.codex-backups` for pending journals, preserve backups, and only then remove a stale lock manually. |
| `Symlinked` / `Unexpected destination type` | Destination/source/LOCAL.md would redirect to an unsafe path or wrong file kind | Inspect the named path; keep the external target untouched. Do not disable these checks. |
| `Missing ... skills/ or agents/` | The downloaded checkout is incomplete or the installer was separated from its source tree | Use a complete checkout; do not copy only `codex/install.py`. |
| `No enabled Studio MCP found` | The checker did not find an enabled named Roblox/Studio MCP config in inspected paths | Check effective `CODEX_HOME`, project ancestors and home config. This is **NOT CONNECTIVITY-VERIFIED**. |
| `configured as ... NOT CONNECTIVITY-VERIFIED` | A matching server name exists in a config file, but connection has not been tested | Separately authorize a live test in a disposable Studio environment. |
| `Transaction not recoverable` | Journal is already `complete` or `recovered` | Never change the journal state to force recovery; review the completed install instead. |
| `original backup missing` / `destination was edited` / `original backup was modified` | Restoring could silently erase new edits or misreport lost originals | Recovery intentionally refuses. Keep the journal and remaining files, take a copy, then reconcile manually. |
| `Invalid transaction journal` / `Invalid transaction entry` / `Invalid transaction destination` | Recovery journal is malformed or untrusted | Do not hand-edit it to bypass validation; restore from an independent known-good backup or investigate in an isolated fixture. |

## Recovery after an interruption

A forced install is **not crash-atomic**. The installer creates a transaction
directory under the selected scope's `.codex-backups/`, containing
`transaction.json` and any moved originals. Journal states are `pending`,
`complete`, and `recovered`.

1. Confirm the installer process has exited. Verify the scope (personal HOME or
   the explicitly selected project root), including any `CODEX_HOME` effects.
2. Preserve an **independent copy** of the transaction directory, relevant
   destinations and `.codex-install.lock` before touching anything. Never
   delete the transaction or backup to "unlock" an installation.
3. Inspect the journal's `scope_root` and `state`. Only a `pending` journal
   can be recovered. If a lock is stale, remove that *specific* lock manually
   only after confirming no installer owns it; it is not auto-stolen.
4. When recovery is separately authorized, from the **skill-pack repo root** run
   the appropriate **single-line** command. The project path and transaction
   must be from the same scope:

   **Project scope:**

   ```bash
   python codex/install.py --scope project --project-root "/path/to/workspace" --recover "/path/to/workspace/.codex-backups/<transaction-id>"
   ```

   **User scope:**

   ```bash
   python codex/install.py --scope user --recover "~/.codex-backups/<transaction-id>"
   ```

5. Verify resulting skills and `LOCAL.md` before considering another apply.
   A recovery refusal requires manual reconciliation, **not** repeated
   `--force` or editing the journal to claim success.

The recovery verifies generated destinations and original backups against
recorded fingerprints before doing any undo. Missing backups and unexpected
edits fail closed. Although normal tests cover interruptions and rollback,
power failures, durable directory fsync, hostile concurrent mutation, and
fully atomic restoration are **not established**.

## What the installer does not do

It does **not** install Python dependencies, Rojo, Wally, Roblox Studio,
Studio MCP, Blender, or GPU services. It does not authenticate Codex or
verify optional role inheritance and tool isolation. The default install
creates no custom agent TOML, but built-in Codex workers may still exist.

After a clean offline install, consult the [manual runtime validation plan](VALIDATION.md).
Do not claim a passed offline test proves a live Studio MCP connection or a
single-writer security boundary.

## Relevant references

- [Install and recovery reference](README.md)
- [Project overview and offline release evidence](../README.md)
- [Runtime evidence checklist](VALIDATION.md)
