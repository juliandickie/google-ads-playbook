import os, stat, tempfile, unittest
from pathlib import Path
from gads_playbook import auth

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
