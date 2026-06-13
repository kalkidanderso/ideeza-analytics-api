from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .factories import add_views, make_blog, make_country, make_user


class BlogViewsAPITests(TestCase):
    def setUp(self):
        us = make_country("United States", "US")
        de = make_country("Germany", "DE")
        self.alice = make_user(us, "alice")
        bob = make_user(de, "bob")
        add_views(make_blog(self.alice, "A1"), 10)
        add_views(make_blog(self.alice, "A2"), 5)
        add_views(make_blog(bob, "B1"), 3)

    def test_group_by_country(self):
        resp = self.client.post(reverse("blog-views") + "?object_type=country&range=year")
        self.assertEqual(resp.status_code, 200)
        rows = resp.json()["data"]
        top = rows[0]
        # US has the most views, two blogs.
        self.assertEqual(top["x"], "United States")
        self.assertEqual(top["y"], 2)
        self.assertEqual(top["z"], 15)

    def test_group_by_user_with_filter(self):
        body = {"filters": {"eq": {"field": "blog__author__username", "value": "alice"}}}
        resp = self.client.post(
            reverse("blog-views") + "?object_type=user&range=year",
            data=body,
            content_type="application/json",
        )
        rows = resp.json()["data"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["x"], "alice")

    def test_invalid_object_type(self):
        resp = self.client.post(reverse("blog-views") + "?object_type=planet")
        self.assertEqual(resp.status_code, 400)


class TopAPITests(TestCase):
    def setUp(self):
        us = make_country("United States", "US")
        alice = make_user(us, "alice")
        for i in range(12):
            add_views(make_blog(alice, f"Blog {i}"), i + 1)

    def test_top_blogs_capped_at_ten(self):
        resp = self.client.post(reverse("top") + "?top=blog&range=year")
        self.assertEqual(resp.status_code, 200)
        rows = resp.json()["data"]
        self.assertEqual(len(rows), 10)
        # Sorted by views descending.
        zs = [r["z"] for r in rows]
        self.assertEqual(zs, sorted(zs, reverse=True))

    def test_top_blog_exposes_author_as_y(self):
        resp = self.client.post(reverse("top") + "?top=blog&range=year")
        rows = resp.json()["data"]
        # y carries the author for the blog case, not a constant blog count.
        self.assertEqual(rows[0]["y"], "alice")

    def test_invalid_top_type(self):
        resp = self.client.post(reverse("top") + "?top=galaxy")
        self.assertEqual(resp.status_code, 400)


class RangeWindowTests(TestCase):
    def setUp(self):
        us = make_country("United States", "US")
        alice = make_user(us, "alice")
        now = timezone.now()
        blog = make_blog(alice, "Recent")
        # Inside a one-month window.
        add_views(blog, 3, viewed_at=now - timedelta(days=5))
        # Outside a one-month window but inside a one-year window.
        add_views(blog, 7, viewed_at=now - timedelta(days=200))

    def test_range_scopes_to_single_window(self):
        month = self.client.post(reverse("top") + "?top=user&range=month").json()["data"]
        year = self.client.post(reverse("top") + "?top=user&range=year").json()["data"]
        # month sees only the recent 3; year sees all 10. If range leaked a
        # 12x multiplier, month would wrongly include the 200-day-old views.
        self.assertEqual(month[0]["z"], 3)
        self.assertEqual(year[0]["z"], 10)


class PerformanceAPITests(TestCase):
    def setUp(self):
        us = make_country("United States", "US")
        self.alice = make_user(us, "alice")
        now = timezone.now()
        # Two separate months so we get a comparable series.
        blog = make_blog(self.alice, "Old", created_at=now - timedelta(days=40))
        add_views(blog, 4, viewed_at=now - timedelta(days=40))
        recent = make_blog(self.alice, "New", created_at=now - timedelta(days=2))
        add_views(recent, 8, viewed_at=now - timedelta(days=2))

    def test_performance_series_has_growth(self):
        resp = self.client.post(reverse("performance") + "?compare=month")
        self.assertEqual(resp.status_code, 200)
        rows = resp.json()["data"]
        self.assertGreaterEqual(len(rows), 2)
        # First period has no baseline.
        self.assertIsNone(rows[0]["z"])
        # Each row exposes the x/y/z structure.
        self.assertIn("number_of_blogs", rows[0]["x"])

    def test_scope_filtered_by_user(self):
        resp = self.client.post(reverse("performance") + f"?compare=month&user_id={self.alice.id}")
        self.assertEqual(resp.json()["scope"], f"user:{self.alice.id}")
