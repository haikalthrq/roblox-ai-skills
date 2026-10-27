"""P0 regression tests; no real home installation, Studio or network calls."""
import argparse
import contextlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("adapter_p0", ROOT / "codex" / "install.py")
adapter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adapter)


class P0Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.project = self.root / "project"

    def install(self, **changes):
        args = dict(scope="project", project_root=self.project, apply=False,
                    force=False, enable_custom_agents=False,
                    accept_subagent_mcp_inheritance=False)
        args.update(changes)
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return adapter.install(argparse.Namespace(**args))

    def test_dry_run_no_changes(self):
        self.assertEqual(self.install(), 0)
        self.assertFalse(self.project.exists())

    def test_full_skills_and_sequential_instructions(self):
        self.assertEqual(self.install(apply=True), 0)
        base = self.project / ".agents" / "skills"
        self.assertEqual(sum((p / "SKILL.md").exists() for p in base.iterdir()), 11)
        self.assertEqual(list((self.project / ".codex" / "agents").glob("*.toml")), [])
        orchestrator = (base / "roblox-build-orchestrator" / "SKILL.md").read_text()
        self.assertIn("Codex sequential workflow", orchestrator)
        self.assertIn("--mode solo", orchestrator)
        self.assertNotIn("--mode fanout", orchestrator)
        game_skill = (base / "create-roblox-game" / "SKILL.md").read_text()
        self.assertIn("Running it (Codex sequential mode)", game_skill)
        self.assertNotIn("--mode fanout", game_skill)
        self.assertNotIn("FAN OUT THE ASSET BLOCK", game_skill)
        self.assertNotIn("they ARE, by default", game_skill)
        self.assertNotIn('See "Fan out the asset', game_skill)
        new_game = (base / "create-roblox-game" / "scripts" / "new_game.py").read_text()
        self.assertNotIn("--mode fanout", new_game)
        self.assertIn("--mode solo", new_game)
        self.assertNotIn("may be fanned out to parallel workers", new_game)
        studio_helper = (base / "create-roblox-game" / "scripts" / "studio_mcp.py").read_text()
        self.assertNotIn("Claude client's", studio_helper)
        briefs = (base / "roblox-build-orchestrator" / "references" / "stage-briefs.md").read_text()
        self.assertNotIn("spawned in parallel", briefs)
        setup_skill = (base / "roblox-skills-setup" / "SKILL.md").read_text()
        self.assertNotIn("Ask Claude to", setup_skill)
        self.assertNotIn("add it to Claude", setup_skill)


    def test_section_brief_and_research_pipeline_enforce_serial_execution(self):
        self.assertEqual(self.install(apply=True), 0)
        root = self.project / ".agents" / "skills" / "create-roblox-game"
        section_script = root / "scripts" / "section.py"
        lines = section_script.read_text(encoding="utf-8")
        self.assertNotIn("Fan-out workers are allowed", lines)
        brief = subprocess.run(
            [sys.executable, str(section_script), "brief", "3"],
            cwd=self.project, capture_output=True, text=True, timeout=25,
        )
        self.assertEqual(brief.returncode, 0, brief.stderr)
        self.assertIn("process asset stages sequentially", brief.stdout)
        self.assertNotIn("Fan-out workers are allowed", brief.stdout)
        pipeline = (root / "references" / "pipeline.md").read_text(encoding="utf-8")
        self.assertIn("Research genre candidates sequentially", pipeline)
        self.assertIn("Do not spawn market-scout workers", pipeline)
        self.assertNotIn("safest place to rehearse fan-out", pipeline)

    def test_ledger_runtime_recommends_only_sequential_mode(self):
        self.assertEqual(self.install(apply=True), 0)
        ledger = (self.project / ".agents" / "skills"
                  / "roblox-build-orchestrator" / "scripts" / "run_log.py")
        root = self.root / "ledger-runs"
        def call(*args):
            return subprocess.run(
                [sys.executable, str(ledger), *args],
                cwd=self.project, capture_output=True, text=True, timeout=25,
            )
        new = call("init", "--dir", str(root), "--run", "serial")
        self.assertEqual(new.returncode, 0, new.stderr)
        meta = json.loads((root / "serial" / "meta.json").read_text(encoding="utf-8"))
        self.assertEqual(meta["mode"], "solo")
        events = root / "serial" / "events.jsonl"
        with events.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({
                "kind": "start", "stage": "3d-meshes",
                "ts": "2026-01-01T00:00:00+00:00",
            }) + "\n")
            fh.write(json.dumps({
                "kind": "end", "stage": "3d-meshes", "status": "ok",
                "ts": "2026-01-01T04:00:00+00:00",
            }) + "\n")
        review = call("decide", "--dir", str(root), "--run", "serial")
        self.assertEqual(review.returncode, 0, review.stderr)
        self.assertIn("RECOMMENDATION: keep sequential execution", review.stdout)
        self.assertIn("Investigate slow stage", review.stdout)
        self.assertNotIn("RECOMMENDATION: fan out", review.stdout)
        invalid = call("init", "--dir", str(root), "--run", "bad",
                       "--mode", "fanout")
        self.assertNotEqual(invalid.returncode, 0)
        self.assertFalse((root / "bad").exists())

    def test_custom_agents_flag_help_describes_risk_not_isolation(self):
        cli = subprocess.run(
            [sys.executable, str(ROOT / "codex" / "install.py"), "--help"],
            cwd=ROOT, capture_output=True, text=True, timeout=25,
        )
        self.assertEqual(cli.returncode, 0, cli.stderr)
        self.assertIn("MCP-inheritance risk acceptance", " ".join(cli.stdout.split()))
        self.assertNotIn("after verifying runtime tool isolation", cli.stdout)

    def test_mcp_and_relocation(self):
        self.install(apply=True)
        moved = self.root / "moved"
        shutil.move(str(self.project), str(moved))
        script = moved / ".agents" / "skills" / "roblox-skills-setup" / "scripts" / "check_setup.py"
        cfg = moved / ".codex" / "config.toml"
        cfg.parent.mkdir(parents=True, exist_ok=True)
        cwd = moved / "nested"
        cwd.mkdir()
        cfg.write_text('[mcp_servers.roblox-studio]\nenabled = false\n')
        def run():
            result = subprocess.run([sys.executable, str(script), "--json"],
                                    cwd=cwd, capture_output=True, text=True, timeout=20)
            self.assertEqual(result.returncode, 0, result.stderr)
            return json.loads(result.stdout)
        report = run()
        self.assertEqual(len(report["skills"]), 11)
        self.assertTrue(all(v["installed"] for v in report["skills"].values()))
        self.assertIn("No enabled", report["studio_mcp"])
        cfg.write_text('[mcp_servers.roblox-studio]\nenabled = true\n')
        self.assertIn("configured as", run()["studio_mcp"])
        cfg.unlink()
        alternate = self.root / "codex-home"
        alternate.mkdir()
        (alternate / "config.toml").write_text('[mcp_servers.roblox-studio]\ncommand="studio"\n')
        with mock.patch.dict(os.environ, {"CODEX_HOME": str(alternate)}):
            self.assertIn("configured as", run()["studio_mcp"])

    def test_unknown_project_agent_blocks_default(self):
        target = self.project / ".codex" / "agents"
        target.mkdir(parents=True)
        (target / "evil-studio-writer.toml").write_text('name="evil"\n')
        self.assertEqual(self.install(), 0)
        with self.assertRaisesRegex(ValueError, "existing custom agent"):
            self.install(apply=True)
        self.assertFalse((self.project / ".agents").exists())

    def test_user_scope_inside_project_detects_local_agents(self):
        from unittest import mock
        cwd = Path.cwd()
        fake_home = self.root / "other-home"
        local = self.project / ".codex" / "agents"
        local.mkdir(parents=True)
        (local / "evil-studio-writer.toml").write_text('name="evil"\\n')
        try:
            os.chdir(self.project)
            with mock.patch.object(adapter.Path, "home", return_value=fake_home):
                with self.assertRaisesRegex(ValueError, "existing custom agent"):
                    self.install(scope="user", apply=True)
                self.assertFalse((fake_home / ".agents").exists())
        finally:
            os.chdir(cwd)

    def test_global_and_codex_home_agents_block_project(self):
        fakehome = self.root / "fakehome"
        directory = fakehome / ".codex" / "agents"
        directory.mkdir(parents=True)
        (directory / "other.toml").write_text('name="other"\n')
        with mock.patch.object(adapter.Path, "home", return_value=fakehome):
            with self.assertRaisesRegex(ValueError, "existing custom agent"):
                self.install(apply=True)
        alt = self.root / "alt"
        (alt / "agents").mkdir(parents=True)
        (alt / "agents" / "role.toml").write_text('name="role"\n')
        with mock.patch.dict(os.environ, {"CODEX_HOME": str(alt)}):
            with self.assertRaisesRegex(ValueError, "existing custom agent"):
                self.install(apply=True)

    def test_opt_in_requires_risk_acceptance_and_studio_free_config(self):
        with self.assertRaisesRegex(ValueError, "inherit parent MCP"):
            self.install(apply=True, enable_custom_agents=True)
        cfg = self.project / ".codex" / "config.toml"
        cfg.parent.mkdir(parents=True)
        cfg.write_text('[mcp_servers.roblox_studio]\ncommand="studio"\n')
        with self.assertRaisesRegex(ValueError, "Studio MCP"):
            self.install(apply=True, enable_custom_agents=True,
                         accept_subagent_mcp_inheritance=True)
        cfg.write_text('[mcp_servers.roblox_studio]\nenabled = false\n')
        self.assertEqual(self.install(apply=True, enable_custom_agents=True,
                                     accept_subagent_mcp_inheritance=True), 0)
        agents = list((self.project / ".codex" / "agents").glob("*.toml"))
        self.assertEqual(len(agents), 7)
        self.assertTrue(all(tomllib.loads(p.read_text()).get("developer_instructions") for p in agents))

    def test_failure_restores_existing_skills(self):
        # Use small fixtures to deterministically inject failure into the second file move.
        source = self.root / "sources"
        skills, agents = source / "skills", source / "agents"
        agents.mkdir(parents=True)
        (agents / "worker.md").write_text("---\nname: worker\ndescription: Test\n---\nInstructions\n")
        for name in ("first", "second"):
            folder = skills / name
            folder.mkdir(parents=True)
            (folder / "SKILL.md").write_text("---\nname: " + name + "\ndescription: Test\n---\nTest\n")
        with mock.patch.object(adapter, "SKILL_SOURCE", skills), mock.patch.object(adapter, "AGENT_SOURCE", agents):
            self.install(apply=True)
            dest = self.project / ".agents" / "skills"
            for name in ("first", "second"):
                (dest / name / "LOCAL.md").write_text(name + "-personal")
            original_move = shutil.move
            def flaky(src, dst, *args, **kwargs):
                if str(src).endswith(os.sep + "second") and ".codex-backups" not in str(src) and ".codex-backups" not in str(dst):
                    raise OSError("injected copy failure")
                return original_move(src, dst, *args, **kwargs)
            with mock.patch.object(adapter.shutil, "move", side_effect=flaky):
                with self.assertRaisesRegex(RuntimeError, "rollback attempted"):
                    self.install(apply=True, force=True)
            for name in ("first", "second"):
                self.assertEqual((dest / name / "LOCAL.md").read_text(), name + "-personal")

    def test_text_formats_and_names(self):
        self.assertTrue({".js", ".yaml", ".yml"}.issubset(adapter.TEXT_SUFFIXES))
        text = adapter.replace_claude_paths(
            r"%USERPROFILE%\.claude\skills" + "\nAsk Claude to inspect",
            self.project / ".agents" / "skills", self.project / ".codex" / "agents"
        )
        self.assertIn("./.agents/skills", text)
        self.assertIn("Ask Codex to", text)
        p = self.root / "worker.md"
        p.write_text("---\nname: sample_worker\ndescription: A worker\n---\nBody\n")
        self.assertEqual(adapter.split_agent(p)[0], "sample_worker")


if __name__ == "__main__":
    unittest.main()
