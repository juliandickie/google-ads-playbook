"""Safety guard: the plugin must never write to a Google Ads account. This scans the shipped source
for the shapes a write would take (a mutate call, or create/remove/update on a *_service object) and
for any Google Ads service other than the read-only GoogleAdsService."""
import re
import unittest
from pathlib import Path

PKG = Path(__file__).parent.parent / "gads_playbook"
SERVICE_WRITE = re.compile(r"_service\.(create|remove|update)")
GET_SERVICE = re.compile(r'get_service\(\s*["\']([^"\']+)["\']')

class ReadOnlyGuardTests(unittest.TestCase):
    def test_no_mutate_calls_and_only_googleadsservice_referenced(self):
        services = set()
        for path in sorted(PKG.rglob("*.py")):
            text = path.read_text()
            for lineno, line in enumerate(text.splitlines(), 1):
                self.assertNotIn("mutate", line.lower(), f"{path}:{lineno}: possible mutate call: {line.strip()}")
                self.assertIsNone(SERVICE_WRITE.search(line), f"{path}:{lineno}: possible service write call: {line.strip()}")
            for m in GET_SERVICE.finditer(text):
                services.add(m.group(1))
        self.assertEqual(services, {"GoogleAdsService"})

if __name__ == "__main__":
    unittest.main()
