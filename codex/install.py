#!/usr/bin/env python3
"""Install this Claude-originated Roblox skill pack for Codex, without changing the source.

Python 3.11+; standard library only. Dry-run unless --apply is supplied.
"""
from __future__ import annotations

import argparse
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
TEXT_SUFFIXES = {".md", ".py", ".lua", ".luau", ".json", ".sh", ".ps1", ".mjs", ".toml", ".txt"}

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
- Inspect Codex's *actual* subagent/tool capabilities before delegation.
  If custom roles or fan-out are unavailable, run independent asset stages
  sequentially in the main session. Never claim unsupported parallel work ran.
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
    # Keep path rewrites scoped to installed text copies, never source files.
    skill_prefix = "~/.agents/skills" if skill_dir == Path.home() / ".agents" / "skills" else skill_dir.as_posix()
    agent_prefix = "~/.codex/agents" if agent_dir == Path.home() / ".codex" / "agents" else agent_dir.as_posix()
    for before, after in (
        ("~/.claude/skills", skill_prefix),
        ("$HOME/.claude/skills", skill_prefix),
        ("~/.claude/agents", agent_prefix),
        ("$HOME/.claude/agents", agent_prefix),
        ("claude mcp list", "codex mcp list"),
        ("claude mcp add", "codex mcp add"),
        ("Claude Code", "Codex"),
    ):
        text = text.replace(before, after)
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
        if path.name == "SKILL.md":
            match = re.match(r"\A(---\r?\n.*?\r?\n---\r?\n)", after, re.DOTALL)
            if not match:
                raise ValueError(f"Missing SKILL.md YAML front matter: {path}")
            after = after[:match.end()] + CODEX_SKILL_RULES + after[match.end():]
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
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", name) or not description:
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


def install(args: argparse.Namespace) -> int:
    if sys.version_info < (3, 11):
        raise RuntimeError("Python 3.11 or newer is required")
    skill_dir, agent_dir, backup_root = targets(args.scope, args.project_root)
    skills = sorted(p for p in SKILL_SOURCE.iterdir() if p.is_dir() and (p / "SKILL.md").is_file())
    agents = sorted(AGENT_SOURCE.glob("*.md"))
    if not skills or not agents:
        raise RuntimeError("Missing skills/ or agents/ in the checked-out pack")
    paths = [skill_dir / p.name for p in skills] + [agent_dir / (p.stem + ".toml") for p in agents]
    conflicts = [p for p in paths if p.exists()]
    print(f"Scope: {args.scope}; skills: {len(skills)}; roles: {len(agents)}")
    print(f"Skills destination: {skill_dir}")
    print(f"Agent destination: {agent_dir}")
    if conflicts:
        print("Existing destination paths:")
        for path in conflicts:
            print("  " + str(path))
    if not args.apply:
        print("DRY RUN: no files changed. Add --apply to install.")
        if conflicts:
            print("Existing paths require --force; backups and LOCAL.md preservation are then enabled.")
        return 0
    if conflicts and not args.force:
        print("Refusing to overwrite. Re-run with --force to back up existing installs.", file=sys.stderr)
        return 2

    # Assemble the complete install before touching destinations.
    with tempfile.TemporaryDirectory(prefix="roblox-codex-") as temp:
        staged = Path(temp)
        for source in skills:
            adapt_skill(source, staged / "skills" / source.name, skill_dir, agent_dir)
        for source in agents:
            target = staged / "agents" / (source.stem + ".toml")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(agent_toml(source, skill_dir, agent_dir), encoding="utf-8")

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        for label, root, staged_root in (
            ("skills", skill_dir, staged / "skills"),
            ("agents", agent_dir, staged / "agents"),
        ):
            root.mkdir(parents=True, exist_ok=True)
            for item in sorted(staged_root.iterdir()):
                dest = root / item.name
                if dest.exists():
                    backup = backup_root / timestamp / label / item.name
                    backup.parent.mkdir(parents=True, exist_ok=True)
                    if backup.exists():
                        raise FileExistsError(f"Backup already exists: {backup}")
                    # Preserve existing local machine configuration, not secrets.
                    prior_local = dest / "LOCAL.md"
                    local = prior_local.read_bytes() if label == "skills" and prior_local.is_file() else None
                    shutil.move(str(dest), str(backup))
                    if local is not None:
                        (item / "LOCAL.md").write_bytes(local)
                shutil.move(str(item), str(dest))
                print(f"Installed: {dest}")

    print("Codex skill instructions and subagent definitions are installed.")
    print("No dependencies were installed, no tests ran, and no Studio connection was opened.")
    print("See codex/README.md for MCP setup, tool checks, and the first smoke-test gate.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scope", choices=("user", "project"), default="user")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--apply", action="store_true", help="Write files (default is dry-run)")
    parser.add_argument("--force", action="store_true", help="Back up and replace existing installed files")
    return install(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
