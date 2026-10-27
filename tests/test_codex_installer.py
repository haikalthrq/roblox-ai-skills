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


if __name__ == "__main__":
    unittest.main()
