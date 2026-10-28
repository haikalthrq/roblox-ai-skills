"""P2 documentation/installed-copy regressions; no external tools or Studio calls."""
from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("adapter_p2", ROOT / "codex" / "install.py")
adapter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adapter)


class P2DocumentationTests(unittest.TestCase):
    def test_p2_guides_are_present_and_local_links_resolve(self):
        markdown = [
            ROOT / "README.md",
            ROOT / "codex" / "README.md",
            ROOT / "codex" / "TROUBLESHOOTING.md",
            ROOT / "codex" / "VALIDATION.md",
        ]
        for file in markdown:
            self.assertTrue(file.is_file(), str(file))
            content = file.read_text(encoding="utf-8")
            with self.subTest(file=file.name):
                # Ignore absolute/external/anchor-only destinations, but verify
                # every normal relative markdown link is backed by a real file.
                for link in re.findall(r"(?<!!)\[[^\]]+\]\(([^)]+)\)", content):
                    dest = unquote(link.split("#", 1)[0])
                    if not dest or "://" in dest or dest.startswith(("mailto:", "/", "#")):
                        continue
                    self.assertTrue((file.parent / dest).exists(), f"{file}: {link}")

    def test_offline_evidence_is_not_claimed_as_runtime_proof(self):
        overview = (ROOT / "README.md").read_text(encoding="utf-8")
        codex = (ROOT / "codex" / "README.md").read_text(encoding="utf-8")
        validation = (ROOT / "codex" / "VALIDATION.md").read_text(encoding="utf-8")
        self.assertIn("33 tests passed in the independent Linux audit", overview)
        self.assertIn("six CI OS/Python jobs succeeded", overview)
        self.assertIn("P0, P1, and P2 regression tests", overview)
        self.assertIn("37 tests passed in the independent Linux audit", overview)
        self.assertIn("could not independently retrieve each CI job", overview)
        self.assertNotIn("Installer tests (execution not yet verified)", overview)
        self.assertIn("live integration unverified", overview)
        self.assertIn("33 tests passed in the independent Linux audit", codex)
        self.assertIn("six OS/Python CI jobs succeeded", codex)
        self.assertIn("could not retrieve per-job test logs", codex)
        self.assertIn("Status: NOT TESTED", validation)
        self.assertIn("D-228", validation)
        self.assertIn("NOT ENFORCED", validation)
        self.assertIn("separately authorized", validation)

    def test_documented_project_paths_use_one_placeholder(self):
        docs = [
            ROOT / "README.md",
            ROOT / "codex" / "README.md",
            ROOT / "codex" / "TROUBLESHOOTING.md",
        ]
        for path in docs:
            content = path.read_text(encoding="utf-8")
            with self.subTest(path=path.name):
                self.assertNotIn("/path/to/game-repo", content)
                self.assertNotIn("/path/to/project", content)
                self.assertNotIn("/path/to/your/project", content)
                self.assertIn("/path/to/workspace", content)
        troubleshooting = docs[-1].read_text(encoding="utf-8")
        self.assertIn('--recover "~/.codex-backups/<transaction-id>"', troubleshooting)

    def test_troubleshooting_matches_supported_recovery_cli(self):
        troubleshooting = (ROOT / "codex" / "TROUBLESHOOTING.md").read_text(encoding="utf-8")
        self.assertIn("--recover", troubleshooting)
        self.assertIn("--scope project", troubleshooting)
        self.assertIn("--scope user", troubleshooting)
        self.assertIn("stale lock", troubleshooting)
        self.assertIn("original backup missing", troubleshooting)
        self.assertIn("NOT CONNECTIVITY-VERIFIED", troubleshooting)
        help_result = subprocess.run(
            [sys.executable, str(ROOT / "codex" / "install.py"), "--help"],
            capture_output=True, text=True, timeout=20,
        )
        self.assertEqual(help_result.returncode, 0, help_result.stderr)
        for flag in ("--recover", "--project-root", "--force",
                     "--enable-custom-agents", "--accept-subagent-mcp-inheritance"):
            self.assertIn(flag, help_result.stdout)

    def test_generated_codex_text_removes_stale_claude_and_fanout_labels(self):
        with tempfile.TemporaryDirectory(prefix="roblox-p2-docs-") as temp:
            root = Path(temp)
            for name in ("create-roblox-game", "roblox-build-orchestrator"):
                source = ROOT / "skills" / name
                dest = root / "installed" / name
                # These are generated copies, not modifications to Claude sources.
                adapter.adapt_skill(
                    source, dest, root / ".agents" / "skills",
                    root / ".codex" / "agents",
                )
                self.assertTrue((dest / "SKILL.md").is_file())

            game = root / "installed" / "create-roblox-game"
            section = (game / "scripts" / "section.py").read_text(encoding="utf-8")
            preflight = (game / "scripts" / "preflight.py").read_text(encoding="utf-8")
            self.assertNotIn("STAY INSIDE CLAUDE CODE", section)
            self.assertIn("STAY INSIDE CODEX", section)
            self.assertNotIn("fan-out decision", preflight)
            self.assertIn("sequential stage-budget review", preflight)

            orchestrator = root / "installed" / "roblox-build-orchestrator"
            skill = (orchestrator / "SKILL.md").read_text(encoding="utf-8")
            ledger = (orchestrator / "scripts" / "run_log.py").read_text(encoding="utf-8")
            self.assertNotIn("did the fan-out pay off", skill)
            self.assertIn("review sequential stage budgets from measured timings", skill)
            self.assertIn("## Start here (Codex sequential workflow)", skill)
            self.assertIn("Start an approved ledger run with run_log.py init --run NAME --mode solo", skill)
            self.assertNotIn("stage timings and tells you whether the split paid off", skill)
            self.assertNotIn("only set the fan-out decision applies to", ledger)
            self.assertIn("Codex ledger reviews their sequential budgets", ledger)
            self.assertNotIn("--mode fanout", ledger)

            # Source remains unchanged and still carries its Claude wording.
            original = (ROOT / "skills" / "create-roblox-game" / "scripts" / "section.py")
            self.assertIn("STAY INSIDE CLAUDE CODE", original.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
