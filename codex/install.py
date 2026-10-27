#!/usr/bin/env python3
"""Install this Claude-originated Roblox skill pack for Codex, without changing the source.

Python 3.11+; standard library only. Dry-run unless --apply is supplied.
"""
from __future__ import annotations

import argparse
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


def adapt_skill(source: Path, destination: Path, skill_dir: Path, agent_dir: Path) -> None:
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
    conflicts = [p for p in paths if p.exists()]
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
                    if label == "skills" and original_local.is_file():
                        (item / "LOCAL.md").write_bytes(original_local.read_bytes())
                installs.append((item, dest, backup))

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
            for dest in reversed(attempted):
                try:
                    if dest.is_dir() and not dest.is_symlink():
                        shutil.rmtree(dest)
                    elif dest.exists() or dest.is_symlink():
                        dest.unlink()
                except OSError as exc:
                    errors.append(f"could not clear {dest}: {exc}")
            for dest, backup in reversed(saved):
                try:
                    shutil.move(str(backup), str(dest))
                except OSError as exc:
                    errors.append(f"could not restore {dest}: {exc}")
            detail = "; ".join(errors) if errors else "all overwritten destinations restored"
            raise RuntimeError(f"Installation failed; rollback attempted ({detail})") from failure

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
                        help="Explicit opt-in to custom roles after verifying runtime tool isolation")
    parser.add_argument("--accept-subagent-mcp-inheritance", action="store_true",
                        help="Acknowledge potential MCP tool inheritance; only for Studio-free sessions")
    try:
        return install(parser.parse_args())
    except (ValueError, FileExistsError, RuntimeError, OSError) as exc:
        print(f"Install blocked/failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
