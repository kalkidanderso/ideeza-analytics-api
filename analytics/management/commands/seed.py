"""Populate the database with realistic sample data for trying the APIs."""
import random
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from analytics.models import Blog, BlogView, Country, User

COUNTRIES = [("United States", "US"), ("Germany", "DE"), ("India", "IN"), ("Brazil", "BR")]


class Command(BaseCommand):
    help = "Seed sample countries, users, blogs and views."

    def handle(self, *args, **options):
        BlogView.objects.all().delete()
        Blog.objects.all().delete()
        User.objects.all().delete()
        Country.objects.all().delete()

        now = timezone.now()
        countries = [Country.objects.create(name=n, code=c) for n, c in COUNTRIES]

        users = []
        for i in range(12):
            users.append(
                User.objects.create(
                    username=f"author_{i}",
                    country=random.choice(countries),
                    created_at=now - timedelta(days=random.randint(30, 400)),
                )
            )

        blogs = []
        for i in range(40):
            blogs.append(
                Blog.objects.create(
                    title=f"Blog {i}",
                    author=random.choice(users),
                    created_at=now - timedelta(days=random.randint(0, 365)),
                )
            )

        views = []
        for blog in blogs:
            for _ in range(random.randint(5, 80)):
                views.append(
                    BlogView(
                        blog=blog,
                        viewed_at=now - timedelta(days=random.randint(0, 365)),
                    )
                )
        BlogView.objects.bulk_create(views)

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {len(countries)} countries, {len(users)} users, "
                f"{len(blogs)} blogs, {len(views)} views."
            )
        )
