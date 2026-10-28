# Codex Desktop runtime evidence

Tested adapter baseline: `d0e8b91f79a55a394b963a91865e3b58cf3a3742`.

## Scope and provenance

The operator reports these results from a local Codex Desktop session on
Windows with Python 3.14.6, a disposable project-scoped skill installation,
and a disposable Roblox Studio Baseplate named Place1. No custom agents
were installed. No Project Antares assets or game files were involved.

This report records operator-supplied evidence. Muse has not independently
reproduced or audited the runtime results. The earlier Muse offline audit
and CI results are separate evidence; see [adapter validation status](README.md#what-has-and-has-not-been-verified).
No raw logs, screenshots, test IDs or timestamps are supplied here.

## Reported results

| Phase | Result | Observed outcome |
| --- | --- | --- |
| Documentation and installation | PASS | Repository documentation inspected; installer dry-run selected 11 skills and 0 custom agents; project installation produced 210 skill files and one completed transaction journal. Fingerprints verified; source repository clean. |
| Runtime discovery and loading | PASS | 11/11 skills discovered and 11/11 instruction sets loaded, with matching `SKILL.md` paths and front matter. |
| Dependency imports | PASS | NumPy, SciPy, Pillow and Requests imported under Python 3.14.6. This does not establish compatibility for every workflow. |
| Offline map fixture | EXPECTED WARNING ACCEPTED | Minimal fixture returned `RESULT: WARN`, exit code 1, for P11 empty space/no props. This is not a clean zero-warning pass. |
| Offline UI fixture | PASS | HUD generation and verification completed. |
| Offline orchestrator ledger | PASS | Seven synthetic solo-ledger commands completed: `init`, `start`, `end`, `status`, `counter`, `report`, `debts`. No game stages or workers executed. |
| Studio connectivity | PASS | Instance discovery and state query succeeded for the disposable place in Edit Mode. |
| Studio DataModel reads | PASS, limited coverage | Root hierarchy, Workspace and Baseplate inspected. The tree search was truncated; this was not a complete content audit. |
| Reversible Studio mutation | PASS | One uniquely marked empty Folder was created, verified through MCP, then deleted. Its absence was confirmed; baseline Baseplate and SpawnLocation observations remained unchanged. |

## Remaining gaps

- Full end-to-end game creation, the full `roblox-code` pipeline and all
  11 skills' operational workflows are not established.
- Rojo, Wally, Lune, Selene and StyLua were missing from the checked tool
  locations. These prerequisites remain unresolved; installations elsewhere
  were not established.
- Python/Blender compatibility for every workflow and external API or
  credential integrations remain unverified.
- Subagent MCP isolation, technical single-writer enforcement, sandbox
  enforcement and safety under concurrent Studio writes remain unverified.
- Reproducibility across machines has not been established. The report does
  not identify an exact Codex Desktop or Studio version or independently
  authenticate the MCP server implementation.

These observations apply to the tested baseline and environment. They do not
validate later commits or complete the runtime security gate. Follow the
[validation methodology](VALIDATION.md) with separate authorization for
each new test scope. Preserve sequential Studio execution and one primary
writer; instructions alone do not enforce isolation. Project Antares
D-228 remains **UNPROVEN** under that project's acceptance criteria.

Promotion to `main` remains pending a separate Muse audit.
