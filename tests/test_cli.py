import contextlib
import unittest
from io import StringIO
from gads_playbook import cli

class CliHelpTests(unittest.TestCase):
    # R41: registry.register_all is imported and called unconditionally at module top, so every
    # subcommand always shows up in --help; a stray ImportError used to be swallowed silently.
    def test_help_lists_leakage_and_pull(self):
        buf = StringIO()
        with contextlib.redirect_stdout(buf):
            with self.assertRaises(SystemExit) as cm:
                cli.main(["--help"])
        self.assertEqual(cm.exception.code, 0)
        out = buf.getvalue()
        self.assertIn("leakage", out)
        self.assertIn("pull", out)
    def test_every_calculator_threshold_explains_itself(self):
        parser, sub = cli.build_parser()
        cli.registry.register_all(sub, cli.add_common)
        for name in ("misallocate", "windows"):
            for action in sub.choices[name]._actions:
                if action.option_strings and action.dest != "help":
                    self.assertTrue(action.help, f"{name} {action.option_strings[0]} has no help text")

if __name__ == "__main__":
    unittest.main()
