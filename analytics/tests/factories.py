"""Tiny helpers to build test data without repeating boilerplate."""
from django.utils import timezone

from analytics.models import Blog, BlogView, Country, User


def make_country(name="United States", code="US"):
    return Country.objects.create(name=name, code=code)


def make_user(country, username="author"):
    return User.objects.create(
        username=username, country=country, created_at=timezone.now()
    )


def make_blog(author, title="Blog", created_at=None):
    return Blog.objects.create(
        title=title, author=author, created_at=created_at or timezone.now()
    )


def add_views(blog, count, viewed_at=None):
    """Attach `count` view rows to a blog, all at the same timestamp."""
    when = viewed_at or timezone.now()
    BlogView.objects.bulk_create(
        [BlogView(blog=blog, viewed_at=when) for _ in range(count)]
    )
