import unittest
from gads_playbook import io
from gads_playbook.brand import Brand, normalise_text

class TextTests(unittest.TestCase):
    def test_normalise_strips_punctuation_and_case(self):
        self.assertEqual(normalise_text("  NordVital's  Magnesium!  "), "nordvitals magnesium")

class BrandedTests(unittest.TestCase):
    def setUp(self):
        self.b = Brand(["NordVital", "Nord Vital", "nordvitl"])
    def test_whole_word_match(self):
        self.assertTrue(self.b.is_branded("nordvital magnesium reviews"))
        self.assertTrue(self.b.is_branded("buy nord vital sleep"))
    def test_collapsed_match(self):
        self.assertTrue(self.b.is_branded("nordvitalmagnesium"))
    def test_misspelling_token(self):
        self.assertTrue(self.b.is_branded("nordvitl discount code"))
    def test_generic_is_not_branded(self):
        self.assertFalse(self.b.is_branded("magnesium glycinate for sleep"))
        self.assertFalse(self.b.is_branded("nord stream pipeline"))
    def test_from_workspace(self):
        b = Brand.from_workspace({"brand_tokens": ["Acme"]})
        self.assertTrue(b.is_branded("acme widgets"))
    def test_from_workspace_without_brand_tokens_raises_missing_input(self):
        with self.assertRaises(io.MissingInput) as cm:
            Brand.from_workspace({})
        self.assertIn("brand_tokens", str(cm.exception))

class DelimiterTests(unittest.TestCase):
    def test_hyphen_delimited_token_still_matches(self):
        b = Brand(["Nord Vital"])
        self.assertTrue(b.is_branded("nord-vital sleep"))

class ClassifyTests(unittest.TestCase):
    def setUp(self):
        self.b = Brand(["NordVital"])
    def test_name_rules(self):
        self.assertEqual(self.b.classify_campaign("Search | Brand | BOF | AU"), "brand")
        self.assertEqual(self.b.classify_campaign("Search | NonBrand | BOF | Magnesium"), "nonbrand")
        self.assertEqual(self.b.classify_campaign("Search - Non-Brand - Generic"), "nonbrand")
        self.assertEqual(self.b.classify_campaign("Search - non brand"), "nonbrand")
    def test_name_rules_hyphen_underscore_delimited(self):
        self.assertEqual(self.b.classify_campaign("Search-Brand-BOF"), "brand")
        self.assertEqual(self.b.classify_campaign("AU_Brand_Search"), "brand")
        self.assertEqual(self.b.classify_campaign("US-NonBrand-BOF"), "nonbrand")
        self.assertEqual(self.b.classify_campaign("Search_Non-Brand"), "nonbrand")
    def test_keyword_rows_for_other_campaigns_fall_through_to_name_rule(self):
        rows = [{"campaign.name": "Other Campaign", "ad_group_criterion.keyword.text": "magnesium", "metrics.clicks": "50"}]
        self.assertEqual(self.b.classify_campaign("Search 3 - Brand", keyword_rows=rows), "brand")
        self.assertEqual(self.b.classify_campaign("Search 3", keyword_rows=rows), "nonbrand")
    def test_prefiltered_rows_without_campaign_name_key_are_used(self):
        rows = [{"ad_group_criterion.keyword.text": "nordvital", "metrics.clicks": "10"},
                {"ad_group_criterion.keyword.text": "magnesium", "metrics.clicks": "5"}]
        self.assertEqual(self.b.classify_campaign("Whatever Name", keyword_rows=rows), "brand")
    def test_keyword_composition_over_name(self):
        rows = [{"campaign.name": "Search 1", "ad_group_criterion.keyword.text": "nordvital", "metrics.clicks": "10"},
                {"campaign.name": "Search 1", "ad_group_criterion.keyword.text": "nordvital sleep", "metrics.clicks": "10"},
                {"campaign.name": "Search 1", "ad_group_criterion.keyword.text": "magnesium", "metrics.clicks": "5"}]
        self.assertEqual(self.b.classify_campaign("Search 1", keyword_rows=rows), "brand")
        rows2 = [{"campaign.name": "Search 2", "ad_group_criterion.keyword.text": "magnesium", "metrics.clicks": "50"},
                 {"campaign.name": "Search 2", "ad_group_criterion.keyword.text": "nordvital", "metrics.clicks": "10"}]
        self.assertEqual(self.b.classify_campaign("Search 2", keyword_rows=rows2), "nonbrand")
    def test_pmax_by_tag(self):
        self.assertEqual(self.b.classify_campaign("PMax | Capture | Brand allowed", "PERFORMANCE_MAX"), "pmax-capture")
        self.assertEqual(self.b.classify_campaign("PMax | Scaling | Brand excluded", "PERFORMANCE_MAX"), "pmax-scaling")
        self.assertEqual(self.b.classify_campaign("PMax All Products", "PERFORMANCE_MAX"), "pmax-unknown")
        self.assertEqual(self.b.classify_campaign("PMax NonBrand Feed Only", "PERFORMANCE_MAX"), "pmax-scaling")
        self.assertEqual(self.b.classify_campaign("PMax Brand", "PERFORMANCE_MAX"), "pmax-capture")

if __name__ == "__main__":
    unittest.main()
