import re
import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.branch_service import generate_branch_name

_VALID_BRANCH_RE = re.compile(r"^(feature|bugfix|refactor|docs|chore)/[a-z0-9]([a-z0-9-]*[a-z0-9])?-\d+$")


class TestBranchClassification(unittest.TestCase):
    def test_bugfix_keywords(self):
        for kw in ["bug", "fix", "broken", "error", "crash", "issue", "patch", "repair", "resolve"]:
            result = generate_branch_name(f"There is a {kw} in the login", 1)
            self.assertTrue(result.startswith("bugfix/"), f"Expected bugfix/ for keyword '{kw}', got {result}")

    def test_refactor_keywords(self):
        for kw in ["refactor", "restructure", "reorganize", "clean up", "cleanup"]:
            result = generate_branch_name(f"Please {kw} the database layer", 2)
            self.assertTrue(result.startswith("refactor/"), f"Expected refactor/ for keyword '{kw}', got {result}")

    def test_docs_keywords(self):
        for kw in ["doc", "documentation", "readme", "comment"]:
            result = generate_branch_name(f"Update the {kw} for the API", 3)
            self.assertTrue(result.startswith("docs/"), f"Expected docs/ for keyword '{kw}', got {result}")

    def test_chore_keywords(self):
        for kw in ["chore", "dependency", "dependencies", "upgrade", "ci", "pipeline"]:
            result = generate_branch_name(f"Run {kw} maintenance tasks", 4)
            self.assertTrue(result.startswith("chore/"), f"Expected chore/ for keyword '{kw}', got {result}")

    def test_default_feature(self):
        result = generate_branch_name("Add user authentication to the app", 5)
        self.assertTrue(result.startswith("feature/"))

    def test_case_insensitive(self):
        result = generate_branch_name("FIX the login BUG", 6)
        self.assertTrue(result.startswith("bugfix/"))


class TestSlugGeneration(unittest.TestCase):
    def test_basic_slug(self):
        result = generate_branch_name("Add user authentication", 10)
        self.assertEqual(result, "feature/add-user-authentication-10")

    def test_special_characters_stripped(self):
        result = generate_branch_name("Fix the login crash!!! @#$%", 11)
        self.assertNotIn("@", result)
        self.assertNotIn("#", result)
        self.assertNotIn("!", result)
        self.assertTrue(result.startswith("bugfix/"))

    def test_unicode_stripped(self):
        result = generate_branch_name("Add emoji support 🎉🚀", 12)
        self.assertTrue(result.startswith("feature/"))
        self.assertRegex(result, r"^[a-z0-9/-]+$")

    def test_no_double_hyphens(self):
        result = generate_branch_name("Fix    multiple   spaces", 13)
        self.assertNotIn("--", result)

    def test_leading_phrases_stripped(self):
        result = generate_branch_name("Please add a new login page", 14)
        self.assertEqual(result, "feature/add-new-login-page-14")

    def test_first_sentence_only(self):
        result = generate_branch_name("Add login page. Then add signup page too.", 15)
        self.assertEqual(result, "feature/add-login-page-15")

    def test_task_id_appended(self):
        result = generate_branch_name("Add feature X", 42)
        self.assertTrue(result.endswith("-42"))

    def test_slashes_replaced_with_hyphens(self):
        result = generate_branch_name("Add input/output validation", 20)
        # Only one slash: the prefix separator
        self.assertEqual(result.count("/"), 1)
        self.assertTrue(result.startswith("feature/"))
        self.assertRegex(result, _VALID_BRANCH_RE)

    def test_dots_replaced_with_hyphens(self):
        result = generate_branch_name("Update config.yaml parser", 21)
        slug = result.split("/", 1)[1]
        self.assertNotIn(".", slug)
        self.assertRegex(result, _VALID_BRANCH_RE)

    def test_underscores_replaced_with_hyphens(self):
        result = generate_branch_name("Rename user_name to username", 22)
        slug = result.split("/", 1)[1]
        self.assertNotIn("_", slug)
        self.assertRegex(result, _VALID_BRANCH_RE)

    def test_filler_words_removed(self):
        result = generate_branch_name("Add the user authentication to the app", 30)
        self.assertTrue(result.startswith("feature/"))
        self.assertNotIn("-the-", result)
        self.assertNotIn("-to-", result)
        self.assertEqual(result, "feature/add-user-authentication-app-30")

    def test_filler_words_kept_when_slug_too_short(self):
        # "to" and "be" are filler words, but removing them leaves < 2 words
        result = generate_branch_name("fix to be", 31)
        self.assertTrue(result.startswith("bugfix/"))
        # Should keep filler words since removing leaves only "fix" (1 word)
        self.assertRegex(result, _VALID_BRANCH_RE)


class TestBranchNamePattern(unittest.TestCase):
    def test_pattern_always_matches(self):
        descriptions = [
            "Add user authentication",
            "Fix the login crash",
            "Refactor database layer",
            "Update the documentation for the API",
            "Run chore maintenance tasks",
            "Add input/output validation",
            "Update config.yaml parser",
            "Rename user_name to username",
        ]
        for desc in descriptions:
            result = generate_branch_name(desc, 1)
            self.assertRegex(result, _VALID_BRANCH_RE,
                             f"Branch name '{result}' does not match valid pattern for desc: {desc}")


class TestLengthTruncation(unittest.TestCase):
    def test_long_description_truncated(self):
        long_desc = "Add a very comprehensive user authentication system with OAuth2 and SAML support including multi-factor authentication"
        result = generate_branch_name(long_desc, 99)
        # prefix + slug + id should be reasonable length
        slug_part = result.split("/", 1)[1].rsplit("-", 1)[0]
        self.assertLessEqual(len(slug_part), 50)

    def test_truncation_at_word_boundary(self):
        long_desc = "Implement distributed caching layer with Redis cluster support and automatic failover mechanisms for production"
        result = generate_branch_name(long_desc, 7)
        slug_part = result.split("/", 1)[1].rsplit("-", 1)[0]
        self.assertFalse(slug_part.endswith("-"))


class TestEdgeCases(unittest.TestCase):
    def test_empty_description(self):
        result = generate_branch_name("", 1)
        self.assertEqual(result, "feature/task-1")

    def test_none_description(self):
        result = generate_branch_name(None, 1)
        self.assertEqual(result, "feature/task-1")

    def test_whitespace_only(self):
        result = generate_branch_name("   \n\t  ", 2)
        self.assertEqual(result, "feature/task-2")

    def test_very_short_description(self):
        result = generate_branch_name("fix it", 42)
        self.assertEqual(result, "bugfix/fix-it-42")

    def test_only_special_chars(self):
        result = generate_branch_name("!@#$%^&*()", 5)
        self.assertTrue(result.endswith(f"-{5}") or "task-5" in result)

    def test_valid_git_branch_chars(self):
        result = generate_branch_name("Add some feature with special chars: ~:?*[\\", 1)
        # Should only contain valid branch chars (alphanumeric, slash, hyphen)
        self.assertRegex(result, r"^[a-z0-9/-]+$")
        self.assertNotIn("//", result)

    def test_no_trailing_dot_lock(self):
        result = generate_branch_name("Update something.lock", 3)
        self.assertFalse(result.endswith(".lock"))
        self.assertFalse(result.endswith("."))


if __name__ == "__main__":
    unittest.main()
