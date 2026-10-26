"""The plugin's own MCP definition must never sit in a root .mcp.json: the host reads that file as a project
config for any session opened in the repository, a worktree under it, or a folder below it, runs it without the
plugin's ${user_config.*} values, and suppresses the plugin's identical server as a duplicate (2026-10-26)."""
import json, unittest
from pathlib import Path
from gads_playbook import __version__

ROOT = Path(__file__).parent.parent

class McpPackagingTests(unittest.TestCase):
    def test_no_root_mcp_json_and_the_manifest_names_the_definition(self):
        self.assertFalse((ROOT / ".mcp.json").exists())
        manifest = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text())
        path = ROOT / manifest["mcpServers"]
        self.assertTrue(path.exists(), path)
        server = json.loads(path.read_text())["mcpServers"]["google-ads"]
        self.assertIn("google-ads-mcp.git@", " ".join(server["args"]))      # pinned to a commit, never a branch
        self.assertEqual(server["env"]["GOOGLE_APPLICATION_CREDENTIALS"], "${user_config.adc_path}")
        self.assertTrue(set(k.split(".")[1].rstrip("}") for k in server["env"].values()) <= set(manifest["userConfig"]))

    def test_versions_move_together(self):
        manifest = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text())
        market = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text())
        self.assertEqual({manifest["version"], market["metadata"]["version"], market["plugins"][0]["version"]}, {__version__})

if __name__ == "__main__":
    unittest.main()
