import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Country",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120, unique=True)),
                ("code", models.CharField(max_length=2, unique=True)),
            ],
        ),
        migrations.CreateModel(
            name="User",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("username", models.CharField(max_length=150, unique=True)),
                ("created_at", models.DateTimeField()),
                ("country", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="users", to="analytics.country")),
            ],
        ),
        migrations.CreateModel(
            name="Blog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=255)),
                ("created_at", models.DateTimeField()),
                ("author", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="blogs", to="analytics.user")),
            ],
        ),
        migrations.CreateModel(
            name="BlogView",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("viewed_at", models.DateTimeField()),
                ("blog", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="views", to="analytics.blog")),
            ],
        ),
        migrations.AddIndex(
            model_name="blogview",
            index=models.Index(fields=["viewed_at"], name="analytics_b_viewed__idx"),
        ),
    ]
