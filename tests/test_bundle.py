import shutil, tempfile, unittest, zipfile
from pathlib import Path
from gads_playbook import bundle, io

ROOT = Path(__file__).resolve().parents[1]

class BundleTests(unittest.TestCase):
    def test_build_writes_expected_files(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "bundle"
            paths = bundle.build(ROOT / "references", ROOT / "assets", out)
            names = sorted(p.name for p in paths)
            self.assertIn("01-brand-kit.md", names)
            self.assertIn("09-PROJECT-INSTRUCTIONS.md", names)
            self.assertIn("prompts.md", names)
            self.assertIn("SETUP.md", names)
            self.assertIn("google-ads-claude-project.zip", names)
            with zipfile.ZipFile(out / "google-ads-claude-project.zip") as z:
                members = z.namelist()
            self.assertIn("knowledge/06-google-audit-checklist.md", members)
            self.assertIn("prompts.md", members)
            self.assertIn("SETUP.md", members)
            self.assertEqual((out / "knowledge" / "02-google-ads-architecture.md").read_text(),
                             (ROOT / "references" / "02-google-ads-architecture.md").read_text())
    def test_content_matches_the_published_bundle_when_present(self):
        pub = Path.home() / "code" / "google-ads-audit-prompt-library" / "claude-project" / "knowledge"
        if not pub.exists():
            self.skipTest("published bundle not on this machine")
        with tempfile.TemporaryDirectory() as d:
            bundle.build(ROOT / "references", ROOT / "assets", Path(d))
            for f in sorted((Path(d) / "knowledge").glob("*.md")):
                self.assertEqual(f.read_text(), (pub / f.name).read_text(), f.name)
    def test_stale_knowledge_file_is_not_zipped_but_reported(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "bundle"
            (out / "knowledge").mkdir(parents=True)
            stale_file = out / "knowledge" / "99-stale-leftover.md"
            stale_file.write_text("old content that no longer has a source reference")
            stale = []
            bundle.build(ROOT / "references", ROOT / "assets", out, stale=stale)
            with zipfile.ZipFile(out / "google-ads-claude-project.zip") as z:
                members = z.namelist()
            self.assertNotIn("knowledge/99-stale-leftover.md", members)
            self.assertTrue(stale_file.exists())
            self.assertEqual(stale_file.read_text(), "old content that no longer has a source reference")
            self.assertIn(stale_file, stale)
    def test_missing_reference_raises_missing_input_naming_it(self):
        with tempfile.TemporaryDirectory() as d:
            refs = Path(d) / "references"
            refs.mkdir()
            for name in bundle.KNOWLEDGE:
                if name == "06-google-audit-checklist.md":
                    continue
                shutil.copyfile(ROOT / "references" / name, refs / name)
            shutil.copyfile(ROOT / "references" / bundle.PROMPTS, refs / bundle.PROMPTS)
            out = Path(d) / "bundle"
            with self.assertRaises(io.MissingInput) as ctx:
                bundle.build(refs, ROOT / "assets", out)
            self.assertIn("06-google-audit-checklist.md", str(ctx.exception))

if __name__ == "__main__":
    unittest.main()
