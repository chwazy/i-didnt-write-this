import sys
import os
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Stub heavy imports that aren't needed for these unit tests
sys.modules.setdefault("docker", MagicMock())
sys.modules.setdefault("dotenv", MagicMock())
# Provide a load_dotenv no-op so main.py's module-level call doesn't fail
import types
dotenv_mod = types.ModuleType("dotenv")
dotenv_mod.load_dotenv = lambda *a, **kw: None
sys.modules["dotenv"] = dotenv_mod


class TestEstimateCost(unittest.TestCase):
    """Unit tests for _estimate_cost() in main.py."""

    def _import(self):
        # Import lazily to avoid triggering DB/Docker side-effects at module level.
        import importlib
        import main as m
        return m

    def test_known_model_cost(self):
        m = self._import()
        cost = m._estimate_cost("claude-sonnet-4-6", 1_000_000, 1_000_000)
        self.assertAlmostEqual(cost, 3.0 + 15.0, places=2)

    def test_unknown_model_falls_back_to_default(self):
        m = self._import()
        cost = m._estimate_cost("some-future-model-xyz", 1_000_000, 0)
        # Default input price is 3.0 per 1M
        self.assertAlmostEqual(cost, 3.0, places=2)

    def test_partial_match(self):
        m = self._import()
        # "claude-haiku-3-5" is a key; a model name containing it should match
        cost = m._estimate_cost("claude-haiku-3-5-20241022", 1_000_000, 0)
        self.assertAlmostEqual(cost, 0.8, places=2)

    def test_zero_tokens(self):
        m = self._import()
        cost = m._estimate_cost("claude-sonnet-4-6", 0, 0)
        self.assertEqual(cost, 0.0)


class TestAggregateUsageBuckets(unittest.TestCase):
    """
    Tests for the get_usage() aggregation logic.

    We patch httpx.get so no real HTTP calls are made.
    """

    def _call_get_usage(self, pages):
        """
        Call get_usage() with a mocked httpx.get that returns *pages* in order.
        Each element of *pages* is a dict that becomes resp.json().
        """
        import main  # noqa: import here to get the decorated app function

        responses = []
        for page_data in pages:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = page_data
            responses.append(mock_resp)

        with patch.dict(os.environ, {"ANTHROPIC_ADMIN_API_KEY": "sk-ant-admin-test"}):
            with patch("httpx.get", side_effect=responses):
                result = main.get_usage()
        return result

    # ------------------------------------------------------------------
    # Core: flat API response shape (each entry is a model × day record)
    # ------------------------------------------------------------------

    def test_single_model_single_page(self):
        page = {
            "data": [
                {
                    "timestamp": "2026-03-01T00:00:00Z",
                    "model": "claude-sonnet-4-6",
                    "input_tokens": 1000,
                    "cache_read_input_tokens": 200,
                    "output_tokens": 500,
                },
            ],
            "has_more": False,
        }
        result = self._call_get_usage([page])

        self.assertEqual(len(result.by_model), 1)
        self.assertEqual(result.by_model[0].model, "claude-sonnet-4-6")
        # total input = input_tokens + cache_read = 1200
        self.assertEqual(result.by_model[0].input_tokens, 1200)
        self.assertEqual(result.by_model[0].output_tokens, 500)
        self.assertEqual(result.total_input_tokens, 1200)
        self.assertEqual(result.total_output_tokens, 500)
        self.assertIsNone(result.error)

    def test_multiple_models_single_page(self):
        """All models returned in one page must all appear in by_model."""
        page = {
            "data": [
                {
                    "timestamp": "2026-03-01T00:00:00Z",
                    "model": "claude-sonnet-4-6",
                    "input_tokens": 1000,
                    "cache_read_input_tokens": 0,
                    "output_tokens": 500,
                },
                {
                    "timestamp": "2026-03-01T00:00:00Z",
                    "model": "claude-haiku-3-5",
                    "input_tokens": 2000,
                    "cache_read_input_tokens": 100,
                    "output_tokens": 800,
                },
                {
                    "timestamp": "2026-03-01T00:00:00Z",
                    "model": "claude-opus-4",
                    "input_tokens": 500,
                    "cache_read_input_tokens": 50,
                    "output_tokens": 200,
                },
            ],
            "has_more": False,
        }
        result = self._call_get_usage([page])

        self.assertEqual(len(result.by_model), 3)
        model_names = {m.model for m in result.by_model}
        self.assertIn("claude-sonnet-4-6", model_names)
        self.assertIn("claude-haiku-3-5", model_names)
        self.assertIn("claude-opus-4", model_names)

    def test_multiple_days_aggregated_per_model(self):
        """Entries for the same model on different days must be summed."""
        page = {
            "data": [
                {
                    "timestamp": "2026-03-01T00:00:00Z",
                    "model": "claude-sonnet-4-6",
                    "input_tokens": 1000,
                    "cache_read_input_tokens": 0,
                    "output_tokens": 400,
                },
                {
                    "timestamp": "2026-03-02T00:00:00Z",
                    "model": "claude-sonnet-4-6",
                    "input_tokens": 500,
                    "cache_read_input_tokens": 100,
                    "output_tokens": 200,
                },
            ],
            "has_more": False,
        }
        result = self._call_get_usage([page])

        self.assertEqual(len(result.by_model), 1)
        entry = result.by_model[0]
        self.assertEqual(entry.model, "claude-sonnet-4-6")
        self.assertEqual(entry.input_tokens, 1600)   # 1000 + (500+100)
        self.assertEqual(entry.output_tokens, 600)

    def test_pagination_fetches_all_models(self):
        """When has_more=True a second page is fetched and both models appear."""
        page1 = {
            "data": [
                {
                    "timestamp": "2026-03-01T00:00:00Z",
                    "model": "claude-sonnet-4-6",
                    "input_tokens": 1000,
                    "cache_read_input_tokens": 0,
                    "output_tokens": 400,
                },
            ],
            "has_more": True,
            "next_page": "page2token",
        }
        page2 = {
            "data": [
                {
                    "timestamp": "2026-03-01T00:00:00Z",
                    "model": "claude-haiku-3-5",
                    "input_tokens": 300,
                    "cache_read_input_tokens": 50,
                    "output_tokens": 120,
                },
            ],
            "has_more": False,
        }
        result = self._call_get_usage([page1, page2])

        self.assertEqual(len(result.by_model), 2)
        model_names = {m.model for m in result.by_model}
        self.assertIn("claude-sonnet-4-6", model_names)
        self.assertIn("claude-haiku-3-5", model_names)

    def test_empty_data_returns_empty_by_model(self):
        page = {"data": [], "has_more": False}
        result = self._call_get_usage([page])

        self.assertEqual(result.by_model, [])
        self.assertEqual(result.total_input_tokens, 0)
        self.assertEqual(result.total_output_tokens, 0)
        self.assertIsNone(result.error)

    def test_no_api_key_returns_error(self):
        import main

        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("ANTHROPIC_ADMIN_API_KEY", None)
            os.environ.pop("ANTHROPIC_API_KEY", None)
            result = main.get_usage()

        self.assertIsNotNone(result.error)
        self.assertEqual(result.by_model, [])

    def test_api_error_returns_error_response(self):
        import main

        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.text = "Unauthorized"

        with patch.dict(os.environ, {"ANTHROPIC_ADMIN_API_KEY": "sk-ant-admin-test"}):
            with patch("httpx.get", return_value=mock_resp):
                result = main.get_usage()

        self.assertIsNotNone(result.error)
        self.assertIn("401", result.error)
        self.assertEqual(result.by_model, [])

    def test_totals_match_sum_of_by_model(self):
        page = {
            "data": [
                {
                    "timestamp": "2026-03-01T00:00:00Z",
                    "model": "claude-sonnet-4-6",
                    "input_tokens": 1000,
                    "cache_read_input_tokens": 200,
                    "output_tokens": 500,
                },
                {
                    "timestamp": "2026-03-01T00:00:00Z",
                    "model": "claude-haiku-3-5",
                    "input_tokens": 400,
                    "cache_read_input_tokens": 100,
                    "output_tokens": 300,
                },
            ],
            "has_more": False,
        }
        result = self._call_get_usage([page])

        expected_input = sum(m.input_tokens for m in result.by_model)
        expected_output = sum(m.output_tokens for m in result.by_model)
        self.assertEqual(result.total_input_tokens, expected_input)
        self.assertEqual(result.total_output_tokens, expected_output)


if __name__ == "__main__":
    unittest.main()
