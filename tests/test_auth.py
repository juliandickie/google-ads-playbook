import argparse, os, stat, subprocess, tempfile, unittest
from pathlib import Path
from unittest import mock
from gads_playbook import auth, io

class AuthFilesTests(unittest.TestCase):
    def test_writes_adc_and_yaml_with_0600(self):
        with tempfile.TemporaryDirectory() as d:
            paths = auth.write_credential_files(Path(d), "cid", "csec", "rtok", "DEVTOKEN", "1234567890")
            adc = paths["adc"].read_text()
            self.assertIn('"type": "authorized_user"', adc)
            self.assertIn('"refresh_token": "rtok"', adc)
            y = paths["yaml"].read_text()
            self.assertIn("developer_token: DEVTOKEN", y)
            self.assertIn("login_customer_id: 1234567890", y)
            self.assertIn("use_proto_plus: true", y)
            for p in paths.values():
                self.assertEqual(stat.S_IMODE(os.stat(p).st_mode), 0o600)

    def test_overwrites_preexisting_world_readable_file_as_0600(self):
        # Ruling R27: a pre-existing 0o644 file must end at 0o600, not keep its old mode.
        with tempfile.TemporaryDirectory() as d:
            pre = Path(d) / "adc.json"
            pre.write_text("stale")
            os.chmod(pre, 0o644)
            self.assertEqual(stat.S_IMODE(os.stat(pre).st_mode), 0o644)
            paths = auth.write_credential_files(Path(d), "cid", "csec", "rtok", "DEVTOKEN", "1234567890")
            self.assertEqual(stat.S_IMODE(os.stat(paths["adc"]).st_mode), 0o600)

class ReadOpTests(unittest.TestCase):
    # Ruling R26: a missing op binary or a failed op read must raise io.MissingInput naming the
    # reference and the op error text, never a raw traceback out of cmd_auth.
    def test_missing_op_binary_raises_missing_input_naming_the_ref(self):
        with mock.patch("subprocess.run", side_effect=FileNotFoundError()):
            with self.assertRaises(io.MissingInput) as cm:
                auth._read_op("op://x/y/z")
            self.assertIn("op://x/y/z", str(cm.exception))

    def test_op_read_failure_raises_missing_input_with_stderr(self):
        err = subprocess.CalledProcessError(1, ["op"], stderr="not signed in")
        with mock.patch("subprocess.run", side_effect=err):
            with self.assertRaises(io.MissingInput) as cm:
                auth._read_op("op://x/y/z")
            self.assertIn("not signed in", str(cm.exception))

class CmdAuthNormalisationTests(unittest.TestCase):
    # R38: cmd_auth writes the dash-stripped login customer id into google-ads.yaml, matching pull's
    # own normalisation, so a manager id pasted with dashes from the Google Ads UI still works.
    def test_login_customer_id_dashes_stripped_in_yaml(self):
        with tempfile.TemporaryDirectory() as d:
            config_dir = Path(d) / "config"
            client_json = Path(d) / "client.json"
            client_json.write_text("{}")
            args = argparse.Namespace(client_json=str(client_json), login_customer_id="123-456-7890",
                                      developer_token="DEVTOKEN", op_ref=None)
            with mock.patch.object(auth, "CONFIG_DIR", config_dir), \
                 mock.patch.object(auth, "run_oauth", return_value=("c", "s", "r")):
                self.assertEqual(auth.cmd_auth(args), 0)
            yaml_text = (config_dir / "google-ads.yaml").read_text()
            self.assertIn("login_customer_id: 1234567890", yaml_text)
            self.assertNotIn("123-456-7890", yaml_text)
