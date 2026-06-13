from django.db import models


class Country(models.Model):
    name = models.CharField(max_length=120, unique=True)
    code = models.CharField(max_length=2, unique=True)

    def __str__(self):
        return self.name


class User(models.Model):
    username = models.CharField(max_length=150, unique=True)
    # Where the user is based. Lets us roll blog stats up to a country.
    country = models.ForeignKey(
        Country, on_delete=models.CASCADE, related_name="users"
    )
    created_at = models.DateTimeField()

    def __str__(self):
        return self.username


class Blog(models.Model):
    title = models.CharField(max_length=255)
    author = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="blogs"
    )
    created_at = models.DateTimeField()

    def __str__(self):
        return self.title


class BlogView(models.Model):
    """One row per view event, so we can aggregate over any time range."""

    blog = models.ForeignKey(
        Blog, on_delete=models.CASCADE, related_name="views"
    )
    viewed_at = models.DateTimeField()

    class Meta:
        indexes = [models.Index(fields=["viewed_at"])]
