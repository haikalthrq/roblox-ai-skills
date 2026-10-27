"""P1 installer reliability tests: all filesystem effects in temporary directories.

The tests intentionally simulate interruption and contention; they do not run
Codex, Roblox Studio, or a live user-scope installer.
"""
from __future__ import annotations

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
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("adapter_p1", ROOT / "codex" / "install.py")
adapter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adapter)


class P1ReliabilityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="roblox-p1-test-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.project = self.root / "project"

    def args(self, **kwargs):
        opts = dict(
            scope="project", project_root=self.project,
            apply=True, force=False, enable_custom_agents=False,
            accept_subagent_mcp_inheritance=False, recover=None,
        )
        opts.update(kwargs)
        return argparse.Namespace(**opts)

    def install(self, **kwargs):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return adapter.install(self.args(**kwargs))

    def journal_dirs(self, state=None):
        result = []
        for manifest in self.project.glob(".codex-backups/*/transaction.json"):
            data = json.loads(manifest.read_text(encoding="utf-8"))
            if state is None or data["state"] == state:
                result.append(manifest.parent)
        return result

    def interrupted_install(self, force=False):
        native_move = shutil.move
        marker = {"hit": 0}
        def interrupt(source, destination, *args, **kwargs):
            # Interrupt before second staged skill is installed. The original
            # destination may already be in backup on a --force reinstall.
            if "roblox-codex-" in str(source) and ".codex-backups" not in str(source):
                marker["hit"] += 1
                if marker["hit"] == 2:
                    raise KeyboardInterrupt("simulated hard interruption")
            return native_move(source, destination, *args, **kwargs)
        with mock.patch.object(adapter.shutil, "move", side_effect=interrupt):
            with contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(KeyboardInterrupt):
                    adapter.install(self.args(force=force))
        self.assertEqual(marker["hit"], 2)
        self.assertFalse((self.project / ".codex-install.lock").exists())
        txns = self.journal_dirs("pending")
        self.assertEqual(len(txns), 1)
        return txns[0]

    def test_dry_run_does_not_create_lock_or_journal(self):
        self.assertEqual(self.install(apply=False), 0)
        self.assertFalse(self.project.exists())

    def test_exclusive_lock_prevents_second_writer(self):
        with adapter.installation_lock(self.project):
            self.assertTrue((self.project / ".codex-install.lock").is_file())
            with self.assertRaisesRegex(RuntimeError, "Installer lock exists"):
                self.install()
            self.assertFalse((self.project / ".agents").exists())
        self.assertFalse((self.project / ".codex-install.lock").exists())
        self.assertEqual(self.install(), 0)

    def test_complete_transaction_cannot_be_recovered(self):
        self.assertEqual(self.install(), 0)
        txns = self.journal_dirs("complete")
        self.assertEqual(len(txns), 1)
        manifest = json.loads((txns[0] / "transaction.json").read_text(encoding="utf-8"))
        self.assertEqual(len(manifest["entries"]), 11)
        self.assertTrue(all(len(entry["sha256"]) == 64 for entry in manifest["entries"]))
        self.assertFalse((self.project / ".codex-install.lock").exists())
        with self.assertRaisesRegex(ValueError, "not recoverable"):
            adapter.recover_transaction(self.args(recover=txns[0]))

    def test_fresh_interruption_can_remove_partial_generated_tree(self):
        txn = self.interrupted_install()
        assert (self.project / ".agents" / "skills" / "create-roblox-game").exists()
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(adapter.recover_transaction(self.args(recover=txn)), 0)
        self.assertFalse((self.project / ".agents" / "skills" / "create-roblox-game").exists())
        self.assertEqual(self.journal_dirs("recovered"), [txn])
        self.assertFalse((self.project / ".codex-install.lock").exists())

    def test_force_interruption_recovers_previous_skills_and_local_md(self):
        self.assertEqual(self.install(), 0)
        skill_root = self.project / ".agents" / "skills"
        original = (skill_root / "create-roblox-game" / "SKILL.md").read_bytes()
        custom = skill_root / "create-roblox-game" / "LOCAL.md"
        custom.write_text("user notes are preserved", encoding="utf-8")
        txn = self.interrupted_install(force=True)
        self.assertTrue((txn / "skills" / "create-roblox-game").exists())
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(adapter.recover_transaction(self.args(recover=txn)), 0)
        self.assertEqual((skill_root / "create-roblox-game" / "SKILL.md").read_bytes(), original)
        self.assertEqual(custom.read_text(encoding="utf-8"), "user notes are preserved")
        self.assertTrue((skill_root / "roblox-3d-model" / "SKILL.md").is_file())
        self.assertEqual(self.journal_dirs("recovered"), [txn])

    def test_rollback_restores_backup_even_if_move_raises_after_completion(self):
        self.assertEqual(self.install(), 0)
        target = self.project / ".agents" / "skills" / "create-roblox-game"
        original = (target / "SKILL.md").read_bytes()
        (target / "LOCAL.md").write_text("preserve me", encoding="utf-8")
        native_move = shutil.move
        injected = {"hit": False}

        def moved_then_failed(source, destination, *args, **kwargs):
            if (not injected["hit"] and
                    Path(source).resolve() == target.resolve() and
                    ".codex-backups" in Path(destination).parts):
                injected["hit"] = True
                native_move(source, destination, *args, **kwargs)
                raise PermissionError("simulated error after successful rename")
            return native_move(source, destination, *args, **kwargs)

        with mock.patch.object(adapter.shutil, "move", side_effect=moved_then_failed):
            with self.assertRaisesRegex(RuntimeError, "rollback attempted"):
                self.install(force=True)
        self.assertTrue(injected["hit"])
        self.assertEqual((target / "SKILL.md").read_bytes(), original)
        self.assertEqual((target / "LOCAL.md").read_text(encoding="utf-8"), "preserve me")
        self.assertEqual(len(self.journal_dirs("recovered")), 1)

    def test_recovery_refuses_tampered_original_backup(self):
        self.assertEqual(self.install(), 0)
        txn = self.interrupted_install(force=True)
        backup = txn / "skills" / "create-roblox-game" / "SKILL.md"
        self.assertTrue(backup.is_file())
        backup.write_bytes(backup.read_bytes() + b"\n# unexpected backup edit\n")
        with self.assertRaisesRegex(ValueError, "original backup was modified"):
            adapter.recover_transaction(self.args(recover=txn))
        self.assertEqual(self.journal_dirs("pending"), [txn])
        self.assertTrue(backup.is_file())

    def test_recovery_refuses_missing_original_backup_after_interruption(self):
        self.assertEqual(self.install(), 0)
        target = self.project / ".agents" / "skills" / "create-roblox-game"
        (target / "legacy-only.txt").write_text(
            "old artifact that is intentionally absent from the staged copy",
            encoding="utf-8",
        )
        txn = self.interrupted_install(force=True)
        backup = txn / "skills" / "create-roblox-game"
        self.assertTrue(backup.is_dir())
        self.assertTrue(target.is_dir())
        self.assertFalse((target / "legacy-only.txt").exists())
        shutil.rmtree(backup)
        staged_before = adapter.fingerprint(target)
        with self.assertRaisesRegex(ValueError, "original backup missing"):
            adapter.recover_transaction(self.args(recover=txn))
        self.assertEqual(adapter.fingerprint(target), staged_before)
        self.assertEqual(self.journal_dirs("pending"), [txn])
        # Recovery preflights every path; it must not have undone any other
        # still-intact backup when one entry is unrecoverable.
        self.assertTrue((txn / "skills" / "roblox-3d-model").exists())

    def test_recovery_invalid_journal_shapes_fail_cleanly_via_cli(self):
        self.assertEqual(self.install(), 0)
        txn = self.journal_dirs("complete")[0]
        journal = txn / "transaction.json"
        original = json.loads(journal.read_text(encoding="utf-8"))
        original["state"] = "pending"
        expected = adapter.fingerprint(
            self.project / ".agents" / "skills" / "create-roblox-game"
        )

        broken_entry = dict(original)
        broken_entry["entries"] = [123]
        non_string_destination = json.loads(json.dumps(original))
        non_string_destination["entries"][0]["destination"] = 123
        cases = [
            ("non-object document", [], "expected a JSON object"),
            ("non-object entry", broken_entry, "expected a JSON object"),
            ("non-string destination", non_string_destination, "expected a string"),
        ]
        for label, malformed, error_message in cases:
            with self.subTest(label=label):
                journal.write_text(json.dumps(malformed), encoding="utf-8")
                cli = subprocess.run(
                    [sys.executable, str(ROOT / "codex" / "install.py"),
                     "--scope", "project", "--project-root", str(self.project),
                     "--recover", str(txn)],
                    cwd=self.root, capture_output=True, text=True, timeout=20,
                )
                self.assertEqual(cli.returncode, 2, cli.stderr)
                self.assertIn(error_message, cli.stderr)
                self.assertNotIn("Traceback", cli.stderr)
                self.assertEqual(
                    adapter.fingerprint(
                        self.project / ".agents" / "skills" / "create-roblox-game"
                    ), expected
                )
                self.assertFalse((self.project / ".codex-install.lock").exists())

    def test_recovery_refuses_to_remove_post_crash_user_edits(self):
        txn = self.interrupted_install()
        updated = self.project / ".agents" / "skills" / "create-roblox-game" / "SKILL.md"
        updated.write_text(updated.read_text(encoding="utf-8") + "\n# user edit\n", encoding="utf-8")
        before = updated.read_bytes()
        with self.assertRaisesRegex(ValueError, "was edited"):
            adapter.recover_transaction(self.args(recover=txn))
        self.assertEqual(updated.read_bytes(), before)
        self.assertEqual(self.journal_dirs("pending"), [txn])

    def test_recovery_refuses_untrusted_paths_in_manifest(self):
        self.assertEqual(self.install(), 0)
        journal = self.journal_dirs("complete")[0] / "transaction.json"
        data = json.loads(journal.read_text(encoding="utf-8"))
        data["state"] = "pending"
        data["entries"][0]["destination"] = "../../other"
        journal.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Invalid transaction destination"):
            adapter.recover_transaction(self.args(recover=journal.parent))
        self.assertTrue((self.project / ".agents" / "skills" / "create-roblox-game").exists())

    def test_regular_file_cannot_replace_skills_directory(self):
        path = self.project / ".agents" / "skills"
        path.parent.mkdir(parents=True)
        path.write_text("not a directory", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "not a directory"):
            self.install()
        self.assertEqual(path.read_text(encoding="utf-8"), "not a directory")
        self.assertFalse((self.project / ".codex-install.lock").exists())

    def test_symlink_redirects_are_rejected(self):
        source = self.root / "outside"
        source.mkdir()
        (source / "private.txt").write_text("leave alone", encoding="utf-8")
        link = self.project / ".agents"
        link.parent.mkdir(parents=True)
        try:
            os.symlink(str(source), str(link), target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("Creating symlinks not permitted on this runner")
        with self.assertRaisesRegex(ValueError, "Symlinked install directory"):
            self.install()
        self.assertEqual((source / "private.txt").read_text(), "leave alone")

    def test_source_tree_symlinks_are_rejected(self):
        source = self.root / "sample-skill"
        source.mkdir()
        (source / "SKILL.md").write_text("---\nname: sample\ndescription: Test\n---\n")
        private = self.root / "private.txt"
        private.write_text("private")
        try:
            os.symlink(private, source / "extra.txt")
        except (OSError, NotImplementedError):
            self.skipTest("Creating symlinks not permitted on this runner")
        dest = self.root / "converted"
        with self.assertRaisesRegex(ValueError, "Symlink in skill source"):
            adapter.adapt_skill(source, dest, self.project / ".agents" / "skills",
                                self.project / ".codex" / "agents")
        self.assertFalse(dest.exists())

    def test_cli_recovery_rejects_invalid_flag_combinations(self):
        proc = subprocess.run([
            sys.executable, str(ROOT / "codex" / "install.py"),
            "--scope", "project", "--project-root", str(self.project),
            "--recover", str(self.project / ".codex-backups" / "fake"),
            "--apply"
        ], capture_output=True, text=True, timeout=20)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("cannot be combined", proc.stderr)
        self.assertFalse(self.project.exists())


if __name__ == "__main__":
    unittest.main()
