from django.test import TestCase

from analytics.filters import FilterError, apply_filters, build_q
from analytics.models import Blog

from .factories import add_views, make_blog, make_country, make_user


class FilterEngineTests(TestCase):
    def setUp(self):
        us = make_country("United States", "US")
        de = make_country("Germany", "DE")
        self.alice = make_user(us, "alice")
        self.bob = make_user(de, "bob")
        self.a_blog = make_blog(self.alice, "Alpha")
        self.b_blog = make_blog(self.bob, "Beta")

    def test_eq_filters_across_tables(self):
        tree = {"eq": {"field": "author__country__code", "value": "US"}}
        result = apply_filters(Blog.objects.all(), tree, "blog")
        self.assertEqual(list(result), [self.a_blog])

    def test_not_negates(self):
        tree = {"not": {"eq": {"field": "author__username", "value": "alice"}}}
        result = apply_filters(Blog.objects.all(), tree, "blog")
        self.assertEqual(list(result), [self.b_blog])

    def test_and_or_combine(self):
        tree = {
            "or": [
                {"eq": {"field": "author__username", "value": "alice"}},
                {"eq": {"field": "author__username", "value": "bob"}},
            ]
        }
        result = apply_filters(Blog.objects.all(), tree, "blog")
        self.assertEqual(result.count(), 2)

    def test_and_with_three_conditions(self):
        # Three children exercises the _combine loop past the first pair,
        # which a naive two-arg implementation would silently drop.
        tree = {
            "and": [
                {"eq": {"field": "author__country__code", "value": "US"}},
                {"eq": {"field": "author__username", "value": "alice"}},
                {"eq": {"field": "title", "value": "Alpha"}},
            ]
        }
        result = apply_filters(Blog.objects.all(), tree, "blog")
        self.assertEqual(list(result), [self.a_blog])

    def test_or_with_three_conditions(self):
        tree = {
            "or": [
                {"eq": {"field": "title", "value": "Alpha"}},
                {"eq": {"field": "title", "value": "Beta"}},
                {"eq": {"field": "title", "value": "Missing"}},
            ]
        }
        result = apply_filters(Blog.objects.all(), tree, "blog")
        self.assertEqual(result.count(), 2)

    def test_empty_filter_is_noop(self):
        self.assertEqual(apply_filters(Blog.objects.all(), None, "blog").count(), 2)

    def test_unknown_field_is_rejected(self):
        with self.assertRaises(FilterError):
            build_q({"eq": {"field": "author__password", "value": "x"}}, {"title"})

    def test_unknown_operator_is_rejected(self):
        with self.assertRaises(FilterError):
            build_q({"like": {"field": "title", "value": "x"}}, {"title"})

    def test_single_query_no_extra_hits(self):
        # Resolving the tree should still be one query, not one per condition.
        add_views(self.a_blog, 1)
        tree = {"eq": {"field": "author__country__code", "value": "US"}}
        with self.assertNumQueries(1):
            list(apply_filters(Blog.objects.all(), tree, "blog"))
