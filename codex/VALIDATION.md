# Codex–Roblox Studio runtime validation plan

**Status: NOT TESTED.** This document is an operator checklist, not evidence
that the steps below succeeded. The P0–P2 offline adapter and maintenance were
independently audited through `d0e8b91` (38 tests; six passing CI jobs).
CI is a different evidence category from authenticated Codex or Roblox Studio
execution.

## Gate 0 — Explicit authorization

Before any runtime test, obtain separate approval for the exact machine,
**disposable** Roblox project and test scope. Installation, credentials,
MCP configuration, editing the Studio DataModel, writing generated assets,
and running tools are individually permission-gated. Do not reuse
Project Antares assets, its game repository, or its planning-only approvals.

Record the Codex version, operating system, Python version, active working
directory, and whether the session has any shared user/project configurations.
Do not copy API keys or `LOCAL.md` secrets into the report.

## Gate 1 — Offline adapter (already tested at P0–P2)

Record the **exact Git SHA** for the checked-out adapter. In an isolated
temporary workspace and fake HOME, run:

```bash
python -m compileall -q codex tests
python -m unittest discover -s tests -p "test_codex*.py" -v
```

A release claim must cite its own matching CI run and per-platform results,
not a previous commit's tests. This gate validates installer copies,
transaction recovery and safety constraints only.

## Gate 2 — Authenticated Codex skill discovery (NOT TESTED)

With authorization in an **empty disposable project**:

1. Run the dry-run installer and inspect every target. Approve installation
   separately if the target is safe.
2. Restart/open the intended Codex client and request
   `$roblox-skills-setup`, `$roblox-code` and `$create-roblox-game`
   **for read-only inspection**, not generation.
3. Confirm Codex loads the intended installed `SKILL.md` from
   `.agents/skills/` or the approved user path, rather than relying on a
   similar-sounding built-in skill. Record discovery evidence.
4. Distinguish missing prerequisites from installer defects. No project
   creation, code generation, downloads or checks are implied by reading a
   skill.

**Pass criterion:** concrete observed skill discovery for each requested
skill. A file's presence alone is insufficient.

## Gate 3 — Optional subagents / MCP inheritance (NOT TESTED)

Custom roles are disabled by default. To examine inheritance, first use a
separately authorized **Studio-free** Codex session. Inspect the effective
Codex configuration and server/tool exposure; record which tools each role
actually received. A prompt saying "do not use Studio" is not a tool
permission restriction.

In a Studio-connected session, disable and independently verify any
multi-agent functionality at the execution layer. Never assume the adapter's
role TOML or sequential instructions enforce this.

**Pass criterion:** observed effective tool permissions with no Studio MCP
exposure to delegated file workers. If the runtime cannot provide this
boundary, keep all Studio-connected stages sequential and mark isolation
**UNPROVEN**.

## Gate 4 — Studio MCP and single-writer safety (NOT TESTED)

Only after separate approval and using a disposable Studio place:

1. Inspect Codex's effective MCP list and ensure no unintended duplicate
   Studio/Rojo connections. `codex mcp list` is a configuration probe, not a
   connectivity test.
2. Perform a separately approved harmless Studio state/read probe; record the
   actual response, client version and MCP server identifier.
3. If explicitly authorized, use one primary session for one reversible,
   disposable test mutation. Record before/after state and rollback.
4. Verify the agreed single-writer discipline at runtime. Do not deliberately
   create conflicting writes in a valuable game. If multi-writer prevention is
   only an instruction, report it as **NOT ENFORCED**, not as tested isolation.

**Pass criterion:** reproducible MCP connectivity and approved reversible
integration evidence, with the enforcement boundary stated truthfully.

## Gate 5 — Release handoff

Report:

| Item | Evidence to record | Result |
| --- | --- | --- |
| Exact repository SHA | Commit and clean worktree | NOT TESTED |
| Offline test and CI | Commands, counts, six job conclusions | NOT TESTED FOR THIS RUN |
| Authenticated skill discovery | Actual Codex invocation and loaded skill paths | NOT TESTED |
| Custom-agent inherited tools (optional) | Effective available tools, Studio-free session | NOT TESTED |
| Studio MCP connectivity | Actual disposable Studio response | NOT TESTED |
| Single-writer enforcement | Tested mechanism or explicit prompt-only limitation | NOT TESTED |
| No Project Antares access | Fixture paths and authorization boundaries | REQUIRED |

Never change an item to PASS based on docs, adapter file layout, or passing
offline CI alone. Project Antares D-228 stays **UNPROVEN** until separate,
authorized evidence meets that project's acceptance criteria.

## References

- [Codex setup and recovery](README.md)
- [Troubleshooting and stale locks](TROUBLESHOOTING.md)
- [Project overview](../README.md)
