#!/usr/bin/env python3
"""Install this Claude-originated Roblox skill pack for Codex, without changing the source.

Python 3.11+; standard library only. Dry-run unless --apply is supplied.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import os
import uuid
import json
import re
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

PACK_ROOT = Path(__file__).resolve().parent.parent
SKILL_SOURCE = PACK_ROOT / "skills"
AGENT_SOURCE = PACK_ROOT / "agents"
TEXT_SUFFIXES = {".md", ".py", ".lua", ".luau", ".json", ".sh", ".ps1", ".mjs", ".js", ".yml", ".yaml", ".toml", ".txt"}

CODEX_SKILL_RULES = """
## Codex compatibility rules (installed adapter)

This copy was adapted for OpenAI Codex from the upstream Claude Code workflow.
Use Codex's skill discovery and the installed `$<skill-name>` invocation.
The original `skills/` and `agents/` folders remain Claude Code sources.

- A skill supplies instructions and scripts, not permissions, installed tools, or
  a working Roblox Studio connection. Detect dependencies; report missing ones.
- Use the main Codex session as the **only Roblox Studio MCP writer**. Run one
  Studio MCP connection and one Rojo connection. Asset workers may write only
  their individually assigned files/manifests; no worker may interact with Studio.
- In a Studio-connected Codex session, do NOT spawn any subagents (including
  built-in worker/explorer roles). Process asset stages sequentially, even when
  fan-out tools exist. A Studio-free runtime must be separately approved and
  validated before any delegation. Tool permissions are not enforced by prompts.
- Do not treat Claude-only `tools`, `disallowedTools`, `model`, `maxTurns`,
  or `skills` front matter as enforced Codex permission controls.
  The parent Codex session must restrict tools and approve mutations.
- The user must explicitly authorize installation, game/repository changes,
  test execution, asset publication, and any new API/service costs as applicable.
  Planning approval is not permission to build or publish.
- Respect current project decisions and handoff documents before entering
  any automated end-to-end stage. Do not silently replace an existing design,
  roadmap, or acceptance gate with this pack's defaults.
"""

ROLE_PREFIX = """You are a Codex subagent adapted from a Claude Code agent definition.
Follow the designated Roblox skill's SKILL.md and its project decisions.
You are a file-artifact worker, NOT a Roblox Studio operator. Never call Studio
MCP tools, publish assets, or mutate the shared Roblox DataModel. If your task
needs Studio, return a handoff to the primary Codex session instead.
Stay within your assigned output paths; do not modify another worker's files.
The parent session's actual permissions/tool availability govern your work.
Claude-only tool allowlists/denylists and model tiering are not enforceable
from this TOML file. If the requested tooling is unavailable, report that
without claiming completion. Approval is required before writing files or tests.

"""


def targets(scope: str, project_root: Path) -> tuple[Path, Path, Path]:
    root = Path.home() if scope == "user" else project_root.resolve()
    return root / ".agents" / "skills", root / ".codex" / "agents", root / ".codex-backups"


def replace_claude_paths(text: str, skill_dir: Path, agent_dir: Path) -> str:
    """Adapt only installed copies; project-scope examples stay relocatable."""
    personal = skill_dir == Path.home() / ".agents" / "skills"
    skills = "~/.agents/skills" if personal else "./.agents/skills"
    agents = "~/.codex/agents" if personal else "./.codex/agents"
    text = re.sub(r"Claude[ \t]*\r?\n[ \t]*Code", "Codex", text)
    for before, after in (
        ("~/.claude/skills", skills),
        ("$HOME/.claude/skills", skills),
        (r"%USERPROFILE%\.claude\skills", skills),
        ("~/.claude/agents", agents),
        ("$HOME/.claude/agents", agents),
        (r"%USERPROFILE%\.claude\agents", agents),
        ("claude mcp list", "codex mcp list"),
        ("claude mcp add", "codex mcp add"),
        ("Claude\nCode", "Codex"),
        ("Claude Code", "Codex"),
        ("Ask Claude to ", "Ask Codex to "),
        ("ask Claude to ", "ask Codex to "),
        ("Claude client's", "agent client's"),
    ):
        text = text.replace(before, after)
    return text


def replace_once(text: str, old: str, new: str, label: str) -> str:
    """Fail closed when upstream source has changed unexpectedly."""
    if text.count(old) != 1:
        raise ValueError(f"Codex adapter cannot locate {label}: expected exactly one occurrence")
    return text.replace(old, new, 1)


def adapt_python_runtime(source: Path, path: Path, text: str,
                         skill_dir: Path, agent_dir: Path) -> str:
    """Fix executable paths and config discovery in installed copies."""
    if source.name == "roblox-skills-setup" and path.name == "check_setup.py":
        text = replace_once(text,
            'SKILLS_DIR = HOME / ".claude" / "skills"\nAGENTS_DIR = HOME / ".claude" / "agents"',
            'SKILLS_DIR = Path(__file__).resolve().parents[2]\n'
            'AGENTS_DIR = SKILLS_DIR.parents[1] / ".codex" / "agents"',
            "portable setup paths")
        text = replace_once(text, 'AGENTS_DIR.glob("roblox-*.md")',
                            'AGENTS_DIR.glob("*.toml")', "custom-agent format")
        text = replace_once(text, 'SKILLS = [\n',
                            'SKILLS = [\n    "roblox-skills-setup",\n', "setup skill count")
        begin, end = "def studio_mcp() -> str:\n", "\ndef main() -> int:\n"
        if text.count(begin) != 1 or text.count(end) != 1:
            raise ValueError("Cannot locate Studio MCP discovery function")
        prefix, rest = text.split(begin, 1)
        _, suffix = rest.split(end, 1)
        implementation = '''def studio_mcp() -> str:
    """Report configured servers, NOT Studio connectivity."""
    import tomllib

    cfgs = []
    codex_home = os.environ.get("CODEX_HOME")
    if codex_home:
        cfgs.append(Path(codex_home).expanduser() / "config.toml")
    for parent in (Path.cwd(), *Path.cwd().parents):
        cfgs.append(parent / ".codex" / "config.toml")
    cfgs.append(Path.home() / ".codex" / "config.toml")

    seen = set()
    for cfg in cfgs:
        cfg = cfg.resolve()
        if cfg in seen:
            continue
        seen.add(cfg)
        try:
            config = tomllib.loads(cfg.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        servers = config.get("mcp_servers", {})
        if not isinstance(servers, dict):
            continue
        matches = sorted(
            name for name, setting in servers.items()
            if isinstance(name, str) and ("studio" in name.lower() or "roblox" in name.lower())
            and isinstance(setting, dict) and setting.get("enabled") is not False
        )
        if matches:
            return (
                f"configured as {', '.join(matches)} in {cfg}; NOT CONNECTIVITY-VERIFIED. "
                "Check codex mcp list and call get_studio_state with Studio open."
            )
    return (
        "No enabled Studio MCP found in inspected Codex configs; "
        "NOT CONNECTIVITY-VERIFIED. Check codex mcp list and get_studio_state."
    )

'''
        return prefix + implementation + end + suffix
    if source.name == "create-roblox-game" and path.name == "new_game.py":
        text = replace_once(text,
            'CODE_SKILL = Path.home() / ".claude" / "skills" / "roblox-code" / "scripts" / "new_project.py"',
            'CODE_SKILL = Path.home() / ".agents" / "skills" / "roblox-code" / "scripts" / "new_project.py"',
            "global code-skill fallback")
        # Minimal script fixtures contain only the fallback constant. Full
        # upstream new_game.py includes BUILD_MD; adapt it when present and
        # fail closed if its known fan-out defaults change unexpectedly.
        if "BUILD_MD" in text:
            text = replace_once(
                text,
                "may be fanned out to parallel workers (the default; see the",
                "must be processed sequentially in a Studio-connected Codex session (see the",
                "generated BUILD.md sequential stage policy",
            )
            text = replace_once(
                text, "--mode fanout", "--mode solo",
                "generated BUILD.md default ledger mode",
            )
        return text
    if source.name == "create-roblox-game" and path.name == "preflight.py":
        return replace_once(text,
            'SKILLS = Path.home() / ".claude" / "skills"',
            'SKILLS = Path.home() / ".agents" / "skills"',
            "global preflight fallback")
    if source.name == "create-roblox-game" and path.name == "section.py":
        return replace_once(
            text,
            "Fan-out workers are allowed; every one is fanned in and its manifest checked before close.",
            "Studio-connected Codex sessions must process asset stages sequentially; check each manifest before closing the section.",
            "section.py brief and HANDOFF sequential policy",
        )
    if source.name == "roblox-build-orchestrator" and path.name == "run_log.py":
        return codex_run_log(text)
    return text



def codex_orchestrator(text: str) -> str:
    """Replace Claude fan-out defaults in installed Codex instructions only."""
    text = re.sub(
        r"(?m)^description: .*$",
        "description: Runs approved Roblox stages in Codex sequential mode. "
        "Logs handoffs, timings, and single-writer Studio boundaries. "
        "This adapter does not enable parallel workers.",
        text, count=1,
    )

    def section(data: str, start: str, end: str, body: str) -> str:
        if data.count(start) != 1 or data.count(end) != 1:
            raise ValueError(f"Upstream orchestrator headings changed: {start}")
        prefix, remainder = data.split(start, 1)
        _, suffix = remainder.split(end, 1)
        return prefix + body + end + suffix

    text = section(text, "## Start here\n", "## Every run: the ledger\n",
        "## Start here (Codex sequential workflow)\n\n"
        "The default Codex installation does not install custom agents. Built-in "
        "workers may still inherit the primary session's Studio tools, so do "
        "not use fan-out in a Studio-enabled session. Check approval gates.\n\n"
        "Start an approved ledger run with run_log.py init --run NAME --mode solo, "
        "then execute file and Studio stages in order. The ledger checks stall "
        "durations only when invoked; it is not an autonomous timeout.\n\n")
    text = section(text,
        "## Mode B: fan-out (the default for the asset block)\n",
        "## Ending a run\n",
        "## Mode B: fan-out (disabled by default in the Codex adapter)\n\n"
        "Asset work must remain sequential in the primary session when Studio "
        "MCP is present. No TOML role instructions implement an enforceable "
        "Studio MCP deny-list. Separate Studio-free delegation requires a "
        "new runtime security review and explicit authorisation.\n\n"
        "See references/write-boundary.md for the single-writer constraint.\n\n")
    text = text.replace("--mode fanout", "--mode solo")
    return text



def codex_create_game(text: str) -> str:
    """Remove incompatible automatic worker defaults from the installed game skill."""
    start, end = "## Running it\n", "### STAGE 9b: THE INTEGRATION PASS\n"
    if text.count(start) != 1 or text.count(end) != 1:
        raise ValueError("Unexpected create-roblox-game orchestration headings")
    before, rest = text.split(start, 1)
    _, after = rest.split(end, 1)
    text = before + (
        "## Running it (Codex sequential mode)\n\n"
        "Do not fan out any stage when the primary Codex session has Studio MCP. "
        "Optional Codex role TOML is not a tool deny-list; built-in workers may "
        "also inherit parent permissions. Run every asset stage serially, "
        "inspect each manifest, and reserve all Studio writes for one main "
        "session. This overrides any legacy references to fan-out below.\n\n"
        "For an explicitly approved run, initialise the orchestration ledger "
        "with run_log.py init --run NAME --mode solo. Use the established "
        "stage gates and approval boundaries. Do not begin implementation "
        "merely because a planning document was approved.\n\n"
    ) + end + after
    text = replace_once(
        text,
        'they ARE, by default - one `roblox-asset-*` worker each. See "Fan out the asset'
        '\nblock" under Running it for the measurement that changed this.',
        'in Codex Studio sessions, they MUST run sequentially under the primary'
        '\nsession. No asset worker can access Studio; see "Running it" for the'
        '\nCodex sequential stage policy.',
        "create-game early default parallel guidance",
    )
    text = text.replace("--mode fanout", "--mode solo")
    text = text.replace(
        "**Fan-out is allowed inside sections 3 and 4**",
        "**Do not fan out sections 3 and 4 in Codex Studio sessions**",
    )
    return text



def codex_run_log(text: str) -> str:
    """Keep legacy Claude ledger untouched; Codex must not recommend fan-out."""
    start = "def cmd_decide(args) -> None:\n"
    end = "\n# ---------------------------------------------------------------- cli\n"
    if text.count(start) != 1 or text.count(end) != 1:
        raise ValueError("Unexpected run_log.py decision function boundaries")
    before, remaining = text.split(start, 1)
    _, after = remaining.split(end, 1)
    replacement = '''def cmd_decide(args) -> None:
    """Review stage budgets, never recommend Studio-connected subagent fan-out."""
    d = run_dir(Path(args.dir), args.run)
    meta, events = load(d)
    spans = stage_spans(events)
    stages = [stage for stage in meta["plan"] if stage["parallelisable"]]
    measured = [
        (stage["stage"], elapsed_min(spans[stage["stage"]]), stage["budget_min"])
        for stage in stages
        if stage["stage"] in spans and spans[stage["stage"]]["end"]
    ]

    print()
    print(f"SEQUENTIAL STAGE REVIEW for run '{meta['run']}' (mode was {meta['mode']})")
    print("=" * 74)
    print("RECOMMENDATION: keep sequential execution in Studio-connected Codex sessions.")
    print("No custom or built-in subagent is authorised by this ledger.")
    if not measured:
        print("No completed asset stages yet; continue collecting stage measurements.")
        return

    used = sum(item[1] for item in measured)
    budget = sum(item[2] for item in measured)
    over = [item for item in measured if item[1] > item[2]]
    stalls = [event for event in events if event["kind"] == "stall"]
    print(f"Asset stages measured: {len(measured)} of {len(stages)}")
    print(f"Time used: {fmt_min(used)} against {fmt_min(budget)} budget")
    print(f"Over-budget stages: {len(over)}; logged stalls: {len(stalls)}")
    if over:
        worst = max(over, key=lambda item: item[1] - item[2])
        print(f"Investigate slow stage '{worst[0]}' before adding complexity.")
    print("Delegation requires separately approved Studio-free execution and MCP review.")
    print()

'''
    text = before + replacement + end + after
    text = replace_once(
        text,
        "  run_log.py init  --run dry-run-1 [--mode solo|fanout] [--plan default]",
        "  run_log.py init  --run dry-run-1 [--mode solo] [--plan default]",
        "Codex ledger usage mode",
    )
    text = replace_once(
        text,
        's.add_argument("--mode", choices=["solo", "fanout"], default="fanout")',
        's.add_argument("--mode", choices=["solo"], default="solo")',
        "Codex ledger CLI sequential mode",
    )
    text = replace_once(
        text,
        '("decide", cmd_decide, "solo vs fan-out recommendation from measured data")',
        '("decide", cmd_decide, "sequential stage-budget review (no fan-out recommendation)")',
        "Codex ledger CLI review help",
    )
    text = replace_once(
        text,
        "  3. The fan-out decision. Whether the asset block needs subagents is a question\n"
        "     about measured stage durations, and this is where those get measured.",
        "  3. The sequential stage review measures completed asset-stage timings\n"
        "     and recommends improvements without delegating Studio-enabled work.",
        "Codex ledger module documentation",
    )
    text = replace_once(
        text,
        "  run_log.py decide             # solo vs fan-out recommendation from measured data",
        "  run_log.py decide             # sequential stage-budget review",
        "Codex ledger usage instructions",
    )
    return text


def adapt_skill(source: Path, destination: Path, skill_dir: Path, agent_dir: Path) -> None:
    if source.is_symlink() or any(p.is_symlink() for p in source.rglob("*")):
        raise ValueError(f"Symlink in skill source tree refused: {source}")
    shutil.copytree(source, destination)
    for path in destination.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        try:
            before = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        after = replace_claude_paths(before, skill_dir, agent_dir)
        if path.suffix.lower() == ".py":
            after = adapt_python_runtime(source, path, after, skill_dir, agent_dir)
        if path.name == "SKILL.md":
            match = re.match(r"\A(---\r?\n.*?\r?\n---\r?\n)", after, re.DOTALL)
            if not match:
                raise ValueError(f"Missing SKILL.md YAML front matter: {path}")
            after = after[:match.end()] + CODEX_SKILL_RULES + after[match.end():]
        if source.name == "roblox-build-orchestrator" and path.name == "SKILL.md":
            after = codex_orchestrator(after)
        if source.name == "create-roblox-game" and path.name == "SKILL.md":
            after = codex_create_game(after)
        if source.name == "roblox-build-orchestrator" and path.name == "stage-briefs.md":
            after = replace_once(
                after,
                "## roblox-market-scout (one per genre, spawned in parallel)",
                "## roblox-market-scout (sequential in Studio-connected Codex sessions)",
                "stage-briefs Studio-connected scout mode",
            )
        if source.name == "create-roblox-game" and path.name == "pipeline.md":
            after = replace_once(
                after,
                "Use a research skill if you have one (or plain WebSearch/WebFetch), or fan out\n"
                "`roblox-market-scout` across independent genre candidates (this is the safest place to rehearse fan-out - nothing it does\n"
                "touches Studio).",
                "Research genre candidates sequentially using the available research skill or web tools.\n"
                "Do not spawn market-scout workers in a Studio-connected Codex session: built-in\n"
                "and custom subagents can inherit the parent's Studio MCP access.",
                "pipeline research delegation policy",
            )
        # Claude's installer copied Markdown roles. Codex needs generated TOML.
        if source.name == "roblox-build-orchestrator" and path.name == "SKILL.md":
            after = re.sub(
                r"(?m)^mkdir -p [^\n]*?/agents && cp [^\n]*?agents/\*\.md [^\n]*?/agents/?\s*$",
                "# Codex: TOML roles come from codex/install.py; do not copy Claude Markdown agents.",
                after,
            )
        if source.name == "roblox-build-orchestrator" and path.name == "write-boundary.md":
            marker_start = "## Enforce it with the allowlist, not the prompt"
            marker_end = "## The one exception worth naming"
            if marker_start not in after or marker_end not in after:
                raise ValueError("Unknown write-boundary headings: cannot safely adapt tool access")
            if marker_start in after and marker_end in after:
                head, remainder = after.split(marker_start, 1)
                _, tail = remainder.split(marker_end, 1)
                after = (
                    head +
                    "## Codex-enforced tool boundary\n\n"
                    "The upstream Claude `disallowedTools` front matter does not restrict "
                    "Codex subagents. Configure the parent Codex session so asset workers "
                    "cannot access Studio MCP tools; keep one Studio writer in the main "
                    "session. A role prompt alone is not an access-control boundary. "
                    "If effective tool isolation cannot be verified, run the asset "
                    "stages sequentially in the primary session.\n\n" +
                    marker_end + tail
                )
        if after != before:
            path.write_text(after, encoding="utf-8")


def split_agent(source: Path) -> tuple[str, str, list[str], str]:
    raw = source.read_text(encoding="utf-8")
    match = re.match(r"\A---\r?\n(.*?)\r?\n---\r?\n(.*)\Z", raw, re.DOTALL)
    if not match:
        raise ValueError(f"Missing agent front matter: {source}")
    header, body = match.groups()
    metadata: dict[str, str] = {}
    skills: list[str] = []
    in_skills = False
    for line in header.splitlines():
        if line.startswith("  - ") and in_skills:
            skills.append(line[4:].strip())
        elif ":" in line and not line.startswith(" "):
            key, value = line.split(":", 1)
            metadata[key.strip()] = value.strip()
            in_skills = key.strip() == "skills"
        else:
            in_skills = False
    name = metadata.get("name", "")
    description = metadata.get("description", "")
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", name) or not description:
        raise ValueError(f"Invalid agent name/description: {source}")
    return name, description, skills, body


def agent_toml(source: Path, skill_dir: Path, agent_dir: Path) -> str:
    name, description, skills, body = split_agent(source)
    hint = "Required skill(s): " + ", ".join(skills) + ".\n" if skills else ""
    instructions = ROLE_PREFIX + hint + replace_claude_paths(body, skill_dir, agent_dir)
    # JSON double-quoted strings are valid TOML basic strings for these values.
    return (
        "# Generated from agents/" + source.name + " by codex/install.py\n"
        "# Do not infer runtime tool restrictions or model choice from the Claude source.\n"
        + "name = " + json.dumps(name, ensure_ascii=False) + "\n"
        + "description = " + json.dumps(description, ensure_ascii=False) + "\n"
        + "developer_instructions = " + json.dumps(instructions, ensure_ascii=False) + "\n"
    )


def observed_agent_files(agent_dir: Path, scope: str, project_root: Path) -> list[Path]:
    """A default install cannot assume other custom roles are safe or inactive."""
    roots = {agent_dir, Path.home() / ".codex" / "agents"}
    if os.environ.get("CODEX_HOME"):
        roots.add(Path(os.environ["CODEX_HOME"]).expanduser() / "agents")
    # Both scope and invocation context matter: a user-scoped install may
    # be run from a game repo whose project agents are already in effect.
    for context in (project_root.resolve(), Path.cwd().resolve()):
        for parent in (context, *context.parents):
            roots.add(parent / ".codex" / "agents")
    found = set()
    for root in roots:
        if root.is_dir():
            found.update(p.resolve() for p in root.glob("*.toml"))
    return sorted(found)


def studio_config_status(project_root: Path) -> tuple[bool, str]:
    """Conservative preflight, not an assertion about all runtime MCP channels."""
    import tomllib

    roots = {Path.home() / ".codex" / "config.toml"}
    if os.environ.get("CODEX_HOME"):
        roots.add(Path(os.environ["CODEX_HOME"]).expanduser() / "config.toml")
    project_root = project_root.resolve()
    for ancestor in (project_root, *project_root.parents):
        roots.add(ancestor / ".codex" / "config.toml")
    for cfg in sorted(roots):
        if not cfg.is_file():
            continue
        try:
            values = tomllib.loads(cfg.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            return True, f"Unverifiable Codex config {cfg}: {type(exc).__name__}"
        servers = values.get("mcp_servers", {})
        if not isinstance(servers, dict):
            return True, f"Invalid MCP server configuration in {cfg}"
        for name, settings in servers.items():
            if not isinstance(name, str) or not isinstance(settings, dict):
                return True, f"Unverifiable MCP server declaration in {cfg}"
            if settings.get("enabled") is not False and (
                "studio" in name.lower() or "roblox" in name.lower()
            ):
                return True, f"Studio/Roblox MCP {name} is configured in {cfg}"
    return False, "No enabled Studio server in inspected configs; runtime still unverified"



def path_exists(path: Path) -> bool:
    """Path.exists() alone misses dangling symlinks."""
    return path.exists() or path.is_symlink()


def fingerprint(path: Path) -> str:
    """Hash one installed file/tree without following directory symlinks."""
    digest = hashlib.sha256()
    if path.is_symlink():
        raise ValueError(f"Symlink is not an install artifact: {path}")
    if path.is_file():
        digest.update(b"F")
        digest.update(path.read_bytes())
    elif path.is_dir():
        digest.update(b"D")
        for entry in sorted(path.rglob("*"), key=lambda p: p.relative_to(path).as_posix()):
            if entry.is_symlink():
                raise ValueError(f"Symlink inside install artifact: {entry}")
            rel = entry.relative_to(path).as_posix().encode("utf-8")
            digest.update(rel)
            if entry.is_file():
                digest.update(b"F")
                digest.update(entry.read_bytes())
            elif entry.is_dir():
                digest.update(b"D")
            else:
                raise ValueError(f"Unsupported entry in install artifact: {entry}")
    else:
        raise ValueError(f"Not a regular file or directory: {path}")
    return digest.hexdigest()


def assert_safe_targets(skill_dir: Path, agent_dir: Path, backup_root: Path,
                        paths: list[Path]) -> None:
    """Reject redirects, special files, and symlinked destination parents."""
    for folder in (skill_dir.parent, skill_dir, agent_dir.parent, agent_dir, backup_root):
        if folder.is_symlink():
            raise ValueError(f"Symlinked install directory refused: {folder}")
        if folder.exists() and not folder.is_dir():
            raise ValueError(f"Install directory is not a directory: {folder}")
    for dest in paths:
        if dest.is_symlink():
            raise ValueError(f"Symlinked install destination refused: {dest}")
        if dest.exists():
            should_directory = dest.parent == skill_dir
            if should_directory != dest.is_dir():
                raise ValueError(f"Unexpected destination type: {dest}")


@contextmanager
def installation_lock(root: Path):
    """Cross-process O_EXCL lock. A stale lock must be handled manually."""
    if root.is_symlink():
        raise ValueError(f"Symlinked install scope refused: {root}")
    root.mkdir(parents=True, exist_ok=True)
    lock = root / ".codex-install.lock"
    token = uuid.uuid4().hex
    try:
        fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise RuntimeError(
            f"Installer lock exists: {lock}. Another install may be active. "
            "After confirming it has stopped, inspect pending transactions before "
            "removing the stale lock manually."
        ) from exc
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump({"pid": os.getpid(), "token": token,
                       "started": datetime.now(timezone.utc).isoformat()}, stream)
            stream.flush()
            os.fsync(stream.fileno())
        yield
    finally:
        try:
            data = json.loads(lock.read_text(encoding="utf-8"))
            if data.get("token") == token:
                lock.unlink()
        except (OSError, ValueError, TypeError):
            # Do not unlink a lock replaced by another process.
            pass


def write_transaction(path: Path, data: dict) -> None:
    """Replace JSON metadata atomically; the metadata is not a filesystem transaction."""
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    fd = os.open(str(temporary), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        json.dump(data, stream, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)



def transaction_entry(scope_root: Path, dest: Path, item: Path, existed: bool) -> dict:
    return {"destination": dest.relative_to(scope_root).as_posix(),
            "existed": existed, "sha256": fingerprint(item)}


def recover_transaction(args: argparse.Namespace) -> int:
    """Explicit undo for a pending install; refuse user-edited destinations."""
    skill_dir, agent_dir, backup_root = targets(args.scope, args.project_root)
    root = skill_dir.parent.parent
    supplied = args.recover.expanduser()
    if supplied.is_symlink():
        raise ValueError("Symlinked recovery transaction directory refused")
    transaction = supplied.resolve()
    if transaction.parent != backup_root.resolve():
        raise ValueError(f"Recovery requires a direct transaction under {backup_root}")
    with installation_lock(root):
        assert_safe_targets(skill_dir, agent_dir, backup_root, [])
        journal_file = transaction / "transaction.json"
        if journal_file.is_symlink():
            raise ValueError("Symlinked transaction journal refused")
        journal = json.loads(journal_file.read_text(encoding="utf-8"))
        if journal.get("version") != 1 or journal.get("scope_root") != str(root.absolute()):
            raise ValueError("Transaction version or installation root mismatch")
        if journal.get("state") != "pending":
            raise ValueError(f"Transaction not recoverable (state={journal.get('state')})")
        records = journal.get("entries")
        if not isinstance(records, list) or not records:
            raise ValueError("Missing transaction entries")
        entries = []
        for record in records:
            relative = Path(record["destination"])
            parts = relative.parts
            if len(parts) != 3 or parts[:2] not in (
                (".agents", "skills"), (".codex", "agents")
            ) or parts[2] in ("", ".", ".."):
                raise ValueError(f"Invalid transaction destination: {relative}")
            if (not isinstance(record.get("existed"), bool) or
                    not re.fullmatch(r"[0-9a-f]{64}", str(record.get("sha256", "")))):
                raise ValueError(f"Invalid transaction record for {relative}")
            group = "skills" if parts[0] == ".agents" else "agents"
            if group == "agents" and not parts[2].endswith(".toml"):
                raise ValueError("Unrecognized agent destination")
            dest = root / relative
            backup = transaction / group / parts[2]
            if dest.is_symlink() or backup.is_symlink():
                raise ValueError(f"Symlinked transaction destination refused: {dest}")
            entries.append((dest, backup, record))

        assert_safe_targets(skill_dir, agent_dir, backup_root, [r[0] for r in entries])
        # Preflight all entries before undoing the first item. Unrecognized user
        # edits MUST remain untouched; operator must resolve those manually.
        for dest, backup, record in entries:
            if path_exists(dest):
                matches_staged = fingerprint(dest) == record["sha256"]
                if backup.exists() or not record["existed"]:
                    if not matches_staged:
                        raise ValueError(f"Recovery refused: destination was edited: {dest}")
                # No backup means the original destination was never moved
                # (or was already restored). Leave it unchanged; do not guess.
            elif record["existed"] and not backup.exists():
                raise ValueError(f"Recovery refused: original and backup both missing: {dest}")

        for dest, backup, record in reversed(entries):
            if backup.exists():
                if path_exists(dest):
                    if dest.is_dir():
                        shutil.rmtree(dest)
                    else:
                        dest.unlink()
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(backup), str(dest))
                print(f"Restored original: {dest}")
            elif not record["existed"] and path_exists(dest):
                if dest.is_dir():
                    shutil.rmtree(dest)
                else:
                    dest.unlink()
                print(f"Removed new artifact: {dest}")

        journal["state"] = "recovered"
        write_transaction(journal_file, journal)
        print("Recovered pending transaction. Inspect the filesystem before retrying.")
        return 0


def install(args: argparse.Namespace) -> int:
    if sys.version_info < (3, 11):
        raise RuntimeError("Python 3.11 or newer is required")
    skill_dir, agent_dir, backup_root = targets(args.scope, args.project_root)
    skills = sorted(p for p in SKILL_SOURCE.iterdir() if p.is_dir() and (p / "SKILL.md").is_file())
    available_agents = sorted(AGENT_SOURCE.glob("*.md"))
    if not skills or not available_agents:
        raise RuntimeError("Missing skills/ or agents/ in the checked-out pack")

    if args.enable_custom_agents and not args.accept_subagent_mcp_inheritance:
        raise ValueError(
            "Custom agents inherit parent MCP configuration by default. "
            "Review the risk, then explicitly use --accept-subagent-mcp-inheritance "
            "ONLY in a separately isolated, Studio-free Codex session."
        )
    if args.enable_custom_agents:
        configured, reason = studio_config_status(args.project_root)
        if configured:
            raise ValueError(
                "Refusing custom agent installation with Studio MCP or unverifiable "
                f"configuration: {reason}"
            )
        print("WARNING: opting in accepts potential inherited MCP tools. "
              "No Studio isolation is proven by this installer.", file=sys.stderr)
    agents = available_agents if args.enable_custom_agents else []

    previous_roles = observed_agent_files(agent_dir, args.scope, args.project_root)
    if previous_roles and not args.enable_custom_agents:
        print("WARNING: existing Codex custom roles may bypass sequential mode:", file=sys.stderr)
        for path in previous_roles:
            print(f"  {path}", file=sys.stderr)
        if args.apply:
            raise ValueError(
                "Default sequential installation blocked: existing custom agent "
                "TOML files must be disabled or reviewed in every active scope."
            )

    paths = [skill_dir / p.name for p in skills] + [agent_dir / (p.stem + ".toml") for p in agents]
    conflicts = [p for p in paths if path_exists(p)]
    print(f"Scope: {args.scope}; skills: {len(skills)}; roles: {len(agents)} / {len(available_agents)}")
    if not agents:
        print("Sequential workflow policy: no new custom agents installed. "
              "This does NOT disable Codex's built-in workers.")
    print(f"Skills destination: {skill_dir}")
    print(f"Agent destination: {agent_dir}")
    if conflicts:
        print("Existing destination paths:")
        for path in conflicts:
            print("  " + str(path))
    if not args.apply:
        print("DRY RUN: no files changed. Add --apply to install.")
        if conflicts:
            print("Existing paths require --force; backups and LOCAL.md preservation enabled.")
        return 0
    # The dry run intentionally avoids creating even a lock file.
    with installation_lock(skill_dir.parent.parent):
        assert_safe_targets(skill_dir, agent_dir, backup_root, paths)
        # Recheck under lock: the conflict/agent state may have changed since preview.
        if not args.enable_custom_agents and observed_agent_files(agent_dir, args.scope, args.project_root):
            raise ValueError("Existing custom agent TOML discovered after lock acquisition")
        if args.enable_custom_agents:
            configured, reason = studio_config_status(args.project_root)
            if configured:
                raise ValueError(f"Studio MCP detected after lock acquisition: {reason}")
        conflicts = [p for p in paths if path_exists(p)]
        if conflicts and not args.force:
            print("Refusing to overwrite. Use --force to back up existing installs.", file=sys.stderr)
            return 2

        # Assemble and validate every source conversion before touching destinations.
        with tempfile.TemporaryDirectory(prefix="roblox-codex-") as temp:
            staged = Path(temp)
            (staged / "agents").mkdir(parents=True, exist_ok=True)
            for source in skills:
                adapt_skill(source, staged / "skills" / source.name, skill_dir, agent_dir)
            for source in agents:
                target = staged / "agents" / (source.stem + ".toml")
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(agent_toml(source, skill_dir, agent_dir), encoding="utf-8")

            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            backup_base = backup_root / (stamp + "-" + uuid.uuid4().hex[:12])
            installs: list[tuple[Path, Path, Path | None]] = []
            for label, root, staged_root in (
                ("skills", skill_dir, staged / "skills"),
                ("agents", agent_dir, staged / "agents"),
            ):
                for item in sorted(staged_root.iterdir()):
                    dest = root / item.name
                    backup = backup_base / label / item.name if dest.exists() else None
                    if backup is not None:
                        if backup.exists():
                            raise FileExistsError(f"Backup conflict before installation: {backup}")
                        original_local = dest / "LOCAL.md"
                        if label == "skills" and original_local.is_symlink():
                            raise ValueError(f"Symlinked LOCAL.md refused: {original_local}")
                        if label == "skills" and original_local.is_file():
                            (item / "LOCAL.md").write_bytes(original_local.read_bytes())
                    installs.append((item, dest, backup))

            # Write a checksummed, pending undo plan BEFORE the first move.
            scope_root = skill_dir.parent.parent
            journal = {
                "version": 1,
                "state": "pending",
                "scope_root": str(scope_root.absolute()),
                "entries": [
                    transaction_entry(scope_root, dest, item, backup is not None)
                    for item, dest, backup in installs
                ],
            }
            backup_base.mkdir(parents=True, exist_ok=False)
            journal_file = backup_base / "transaction.json"
            write_transaction(journal_file, journal)

            attempted: list[Path] = []
            saved: list[tuple[Path, Path]] = []
            try:
                for item, dest, backup in installs:
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    if backup is not None:
                        backup.parent.mkdir(parents=True, exist_ok=True)
                        shutil.move(str(dest), str(backup))
                        saved.append((dest, backup))
                    attempted.append(dest)
                    shutil.move(str(item), str(dest))
                    print(f"Installed: {dest}")
            except Exception as failure:
                errors = []
                # Moving an original to backup may succeed on disk then raise.
                # Inspect actual backup presence, rather than only in-memory
                # save bookkeeping, to restore those originals as well.
                for item, dest, backup in reversed(installs):
                    if backup is not None and backup.exists():
                        if backup.is_symlink():
                            errors.append(f"symlinked backup refused: {backup}")
                            continue
                        try:
                            if dest.is_dir() and not dest.is_symlink():
                                shutil.rmtree(dest)
                            elif path_exists(dest):
                                dest.unlink()
                            dest.parent.mkdir(parents=True, exist_ok=True)
                            shutil.move(str(backup), str(dest))
                        except OSError as exc:
                            errors.append(f"could not restore {dest}: {exc}")
                    elif backup is None and dest in attempted:
                        try:
                            if dest.is_dir() and not dest.is_symlink():
                                shutil.rmtree(dest)
                            elif path_exists(dest):
                                dest.unlink()
                        except OSError as exc:
                            errors.append(f"could not clear {dest}: {exc}")
                detail = "; ".join(errors) if errors else "all overwritten destinations restored"
                if not errors:
                    journal["state"] = "recovered"
                    write_transaction(journal_file, journal)
                raise RuntimeError(
                    f"Installation failed; rollback attempted ({detail}). "
                    f"Transaction: {backup_base}"
                ) from failure


            journal["state"] = "complete"
            write_transaction(journal_file, journal)

        print("Codex skills installed; custom agents generated only when explicitly opted in.")
        print("No dependencies were installed or Studio connection opened by this installer.")
        return 0



def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scope", choices=("user", "project"), default="user")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--apply", action="store_true", help="Write files (default is dry-run)")
    parser.add_argument("--force", action="store_true", help="Back up and replace existing installed files")
    parser.add_argument("--enable-custom-agents", action="store_true",
                        help="Optional roles require explicit MCP-inheritance risk acceptance in a Studio-free session")
    parser.add_argument("--accept-subagent-mcp-inheritance", action="store_true",
                        help="Acknowledge potential MCP tool inheritance; only for Studio-free sessions")
    parser.add_argument("--recover", type=Path, metavar="TRANSACTION_DIR",
                        help="Undo a pending interrupted transaction after confirming installer is stopped")
    args = parser.parse_args()
    if args.recover and (args.apply or args.force or args.enable_custom_agents):
        parser.error("--recover cannot be combined with --apply, --force or --enable-custom-agents")
    try:
        return recover_transaction(args) if args.recover else install(args)
    except (ValueError, FileExistsError, RuntimeError, OSError) as exc:
        print(f"Install blocked/failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
