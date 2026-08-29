import unittest

from update_service import normalize_repository, release_from_payload, version_tuple


class UpdateServiceTests(unittest.TestCase):
    def test_repository_url_is_normalized(self):
        self.assertEqual(normalize_repository("https://github.com/acme/planner.git"), "acme/planner")

    def test_versions_are_compared_numerically(self):
        self.assertGreater(version_tuple("v1.10.0"), version_tuple("1.9.9"))

    def test_installer_is_found_in_release_assets(self):
        release = release_from_payload(
            {
                "tag_name": "v1.6.0",
                "name": "Version 1.6",
                "html_url": "https://github.com/acme/planner/releases/tag/v1.6.0",
                "assets": [
                    {"name": "source.zip", "browser_download_url": "https://example/source.zip"},
                    {"name": "NIS_Data_Center_Planner_Setup_v1.6.0.exe", "browser_download_url": "https://example/setup.exe"},
                ],
            },
            "1.5.0",
        )
        self.assertTrue(release.is_newer)
        self.assertEqual(release.installer_name, "NIS_Data_Center_Planner_Setup_v1.6.0.exe")

    def test_same_version_is_not_an_update(self):
        release = release_from_payload({"tag_name": "v1.5.0", "assets": []}, "1.5.0")
        self.assertFalse(release.is_newer)


if __name__ == "__main__":
    unittest.main()
