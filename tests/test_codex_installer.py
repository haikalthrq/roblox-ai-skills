"""Offline tests for the Codex installer. Run only with explicit test authorization."""
import importlib.util
import tempfile
import unittest
from pathlib import Path

INSTALLER = Path(__file__).resolve().parents[1] / "codex" / "install.py"
spec = importlib.util.spec_from_file_location("codex_install", INSTALLER)
adapter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adapter)


class CodexInstallerTests(unittest.TestCase):
    def test_agent_conversion_retains_role_and_skill(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "worker.md"
            p.write_text(
                "---\nname: sample-worker\ndescription: Sample agent\n"
                "skills:\n  - roblox-map\nmodel: opus\n---\n"
                "Use the map skill, not Studio.\n",
                encoding="utf-8",
            )
            content = adapter.agent_toml(p, Path(tmp) / "skills", Path(tmp) / "agents")
            import tomllib
            result = tomllib.loads(content)
            self.assertEqual(result["name"], "sample-worker")
            self.assertIn("roblox-map", result["developer_instructions"])
            self.assertNotIn("model = ", content)

    def test_paths_rewrite_to_codex_without_changing_original(self):
        source = "python ~/.claude/skills/roblox-code/scripts/check.py; claude mcp list"
        text = adapter.replace_claude_paths(
            source, Path.home() / ".agents" / "skills", Path.home() / ".codex" / "agents"
        )
        self.assertIn("~/.agents/skills/roblox-code", text)
        self.assertIn("codex mcp list", text)
        self.assertEqual(source, "python ~/.claude/skills/roblox-code/scripts/check.py; claude mcp list")

    def test_frontmatter_is_retained(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            src = base / "src"
            src.mkdir()
            (src / "SKILL.md").write_text(
                "---\nname: abc\ndescription: Do something\n---\n# Body\n",
                encoding="utf-8",
            )
            dest = base / "dest"
            adapter.adapt_skill(src, dest, base / "installed", base / "roles")
            content = (dest / "SKILL.md").read_text(encoding="utf-8")
            self.assertTrue(content.startswith("---\nname: abc"))
            self.assertIn("Codex compatibility rules", content)
            self.assertEqual((src / "SKILL.md").read_text(encoding="utf-8").count("Codex"), 0)


    def test_setup_checks_codex_directories_and_toml(self):
        import ast
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            src = base / "roblox-skills-setup"
            script = src / "scripts" / "check_setup.py"
            script.parent.mkdir(parents=True)
            script.write_text(
                'from pathlib import Path\nHOME = Path.home()\n'
                'SKILLS_DIR = HOME / ".claude" / "skills"\n'
                'AGENTS_DIR = HOME / ".claude" / "agents"\n'
                'def studio_mcp() -> str:\n    return "Claude"\n'
                '\ndef main() -> int:\n'
                '    roles = AGENTS_DIR.glob("roblox-*.md")\n    return 0\n',
                encoding="utf-8",
            )
            output = adapter.adapt_python_runtime(
                src, script, script.read_text(encoding="utf-8"),
                base / "project" / ".agents" / "skills",
                base / "project" / ".codex" / "agents",
            )
            ast.parse(output)
            self.assertIn("roblox-*.toml", output)
            self.assertIn("codex mcp list", output)
            self.assertNotIn('HOME / ".claude" / "skills"', output)
            self.assertIn(str(base / "project" / ".codex" / "agents"), output)

    def test_executable_fallback_paths_relocated(self):
        import ast
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "create-roblox-game"
            for filename, original, expected in (
                ("new_game.py",
                 'CODE_SKILL = Path.home() / ".claude" / "skills" / "roblox-code" / "scripts" / "new_project.py"',
                 'Path(__file__).resolve().parents[2] / "roblox-code"'),
                ("preflight.py",
                 'SKILLS = Path.home() / ".claude" / "skills"',
                 'SKILLS = Path(__file__).resolve().parents[2]'),
            ):
                new = adapter.adapt_python_runtime(
                    src, src / "scripts" / filename,
                    "from pathlib import Path\n" + original + "\n",
                    Path(tmp) / ".agents" / "skills", Path(tmp) / ".codex" / "agents"
                )
                ast.parse(new)
                self.assertIn(expected, new)

    def test_default_install_exposes_no_subagents(self):
        import argparse
        import contextlib
        import io
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            skills = base / "source" / "skills"
            agents = base / "source" / "agents"
            skill = skills / "example"
            skill.mkdir(parents=True)
            agents.mkdir(parents=True)
            (skill / "SKILL.md").write_text(
                "---\nname: example\ndescription: Example\n---\n# Example\n",
                encoding="utf-8",
            )
            (agents / "roblox-asset-map.md").write_text(
                "---\nname: roblox-asset-map\ndescription: Asset map worker\n"
                "skills:\n  - example\n---\nRead data only.\n",
                encoding="utf-8",
            )
            old_skills, old_agents = adapter.SKILL_SOURCE, adapter.AGENT_SOURCE
            try:
                adapter.SKILL_SOURCE, adapter.AGENT_SOURCE = skills, agents
                opts = argparse.Namespace(
                    scope="project", project_root=base / "target",
                    apply=True, force=False,
                    enable_custom_agents=False, confirm_studio_isolation=False,
                )
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(adapter.install(opts), 0)
                self.assertTrue((base / "target" / ".agents" / "skills" / "example" / "SKILL.md").exists())
                self.assertFalse((base / "target" / ".codex" / "agents" / "roblox-asset-map.toml").exists())
                opts.enable_custom_agents = True
                with self.assertRaisesRegex(RuntimeError, "Verify actual tool isolation"):
                    adapter.install(opts)
            finally:
                adapter.SKILL_SOURCE, adapter.AGENT_SOURCE = old_skills, old_agents



if __name__ == "__main__":
    unittest.main()
