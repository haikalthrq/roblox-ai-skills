# Codex–Roblox Studio runtime validation plan

**Status: PARTIALLY VALIDATED, operator-reported.** Windows Codex Desktop
skill discovery/loading and limited disposable Studio MCP checks passed at
`d0e8b91`; runtime security boundaries remain unverified. See
[runtime evidence and limitations](RUNTIME_EVIDENCE.md). Muse has not
independently reproduced or audited these runtime results. The P0–P2 offline
adapter and maintenance were independently audited through `d0e8b91`
(38 tests; six passing CI jobs). This checklist remains the methodology;
offline CI and runtime observations are separate evidence categories.

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

## Gate 2 — Authenticated Codex skill discovery (PASS, tested environment)

The operator reports discovery and instruction loading for 11/11 skills,
with matching installed `SKILL.md` paths and front matter. This establishes
loading in the tested environment, not operational readiness of all skills.

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

## Gate 3 — Optional subagents / MCP inheritance (UNVERIFIED)

No custom agents were installed or exercised in the reported runtime checks.
Subagent inheritance and isolation remain unverified.

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

## Gate 4 — Studio MCP and single-writer safety (PARTIAL)

Operator-reported connectivity, DataModel reads and one reversible Folder
mutation: **PASS** in the disposable place. Tree-search coverage was truncated.
Technical single-writer enforcement: **UNVERIFIED**. These results do not
make the whole runtime security gate PASS.

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
| Exact repository SHA | Tested adapter baseline and clean source | Operator reports `d0e8b91`; see runtime evidence |
| Offline test and CI | Commands, counts, six job conclusions | Historical Muse/CI results at `d0e8b91`; no runtime audit |
| Authenticated skill discovery | Actual Codex invocation and loaded skill paths | PASS, operator-reported 11/11 discovery and loading |
| Custom-agent inherited tools (optional) | Effective available tools, Studio-free session | UNVERIFIED |
| Studio MCP connectivity, reads and reversible write | Disposable Studio responses and before/after observations | PASS, operator-reported; limited read coverage |
| Single-writer enforcement | Tested mechanism or explicit prompt-only limitation | UNVERIFIED |
| No Project Antares access | Fixture scope and authorization boundaries | Operator reports no Antares assets or game files involved |

Never change an item to PASS based on docs, adapter file layout, or passing
offline CI alone. Project Antares D-228 stays **UNPROVEN** until separate,
authorized evidence meets that project's acceptance criteria.

## References

- [Operator-reported Windows runtime evidence](RUNTIME_EVIDENCE.md)
- [Codex setup and recovery](README.md)
- [Troubleshooting and stale locks](TROUBLESHOOTING.md)
- [Project overview](../README.md)
