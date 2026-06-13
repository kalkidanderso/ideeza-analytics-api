from django.test import SimpleTestCase

from analytics.aggregation import growth_pct, resolve_range


class AggregationHelperTests(SimpleTestCase):
    def test_resolve_range_defaults_and_normalises(self):
        self.assertEqual(resolve_range(None), "month")
        self.assertEqual(resolve_range("WEEK"), "week")

    def test_resolve_range_rejects_unknown(self):
        with self.assertRaises(ValueError):
            resolve_range("decade")

    def test_growth_first_period_is_none(self):
        self.assertIsNone(growth_pct(10, None))

    def test_growth_from_zero(self):
        self.assertEqual(growth_pct(5, 0), 100.0)
        self.assertEqual(growth_pct(0, 0), 0.0)

    def test_growth_percentage(self):
        self.assertEqual(growth_pct(150, 100), 50.0)
        self.assertEqual(growth_pct(50, 100), -50.0)
