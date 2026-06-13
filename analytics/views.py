from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from django.db.models import Count

from .aggregation import (
    TRUNC_FUNCS,
    growth_pct,
    resolve_range,
    series_start,
    window_start,
)
from .filters import FilterError, apply_filters
from .models import Blog, BlogView

# Reused across all three endpoints to describe the optional filter body in the docs.
_FILTER_BODY = {
    "type": "object",
    "properties": {
        "filters": {
            "type": "object",
            "description": "Filter tree built from and / or / not / eq.",
            "example": {
                "and": [
                    {"eq": {"field": "blog__author__country__code", "value": "US"}},
                    {"not": {"eq": {"field": "blog__title", "value": "draft"}}},
                ]
            },
        }
    },
}

# Requests can ask for more rows, but we never return more than this.
MAX_ROWS = 1000
DEFAULT_ROWS = 100


class _AnalyticsView(APIView):
    """Small base that pulls the dynamic filter tree out of the request."""

    def filter_tree(self, request):
        # Filters can come from the JSON body (preferred) or be skipped.
        return request.data.get("filters") if request.data else None

    def bad_request(self, message):
        return Response({"error": message}, status=status.HTTP_400_BAD_REQUEST)

    def row_limit(self, request):
        """Clamp a client-supplied ?limit to a safe range."""
        try:
            limit = int(request.query_params.get("limit", DEFAULT_ROWS))
        except (TypeError, ValueError):
            limit = DEFAULT_ROWS
        return max(1, min(limit, MAX_ROWS))


class BlogViewsAnalytics(_AnalyticsView):
    """API #1 - blogs and views grouped by country or user."""

    @extend_schema(
        summary="Blogs and views grouped by country or user",
        parameters=[
            OpenApiParameter("object_type", str, enum=["country", "user"]),
            OpenApiParameter("range", str, enum=["week", "month", "year"]),
            OpenApiParameter("limit", int, description="Max rows (1-1000)."),
        ],
        request=_FILTER_BODY,
    )
    def post(self, request):
        object_type = request.query_params.get("object_type", "country")
        if object_type not in ("country", "user"):
            return self.bad_request("object_type must be 'country' or 'user'.")

        try:
            range_name = resolve_range(request.query_params.get("range"))
            tree = self.filter_tree(request)
            views = apply_filters(BlogView.objects.all(), tree, "view")
        except (ValueError, FilterError) as exc:
            return self.bad_request(str(exc))

        views = views.filter(viewed_at__gte=window_start(range_name))

        # Group key differs by object_type but the aggregation is identical,
        # so we resolve the lookup once and reuse it.
        group_field = (
            "blog__author__country__name"
            if object_type == "country"
            else "blog__author__username"
        )

        rows = (
            views.values(group_field)
            .annotate(
                number_of_blogs=Count("blog", distinct=True),
                total_views=Count("id"),
            )
            .order_by("-total_views")[: self.row_limit(request)]
        )

        data = [
            {
                "x": row[group_field],
                "y": row["number_of_blogs"],
                "z": row["total_views"],
            }
            for row in rows
        ]
        return Response({"object_type": object_type, "range": range_name, "data": data})


class TopAnalytics(_AnalyticsView):
    """API #2 - Top 10 users / countries / blogs by total views."""

    # Each top type maps to its grouping field plus the extra field exposed
    # as y. x/y/z deliberately vary by type, as the spec asks:
    #   user/country -> y = number of blogs
    #   blog         -> y = author (blog count would always be 1 here)
    CONFIG = {
        "user": {"group": "blog__author__username", "y": "blogs"},
        "country": {"group": "blog__author__country__name", "y": "blogs"},
        "blog": {"group": "blog__title", "y": "author", "extra": "blog__author__username"},
    }

    @extend_schema(
        summary="Top 10 users, countries, or blogs by total views",
        parameters=[
            OpenApiParameter("top", str, enum=["user", "country", "blog"]),
            OpenApiParameter("range", str, enum=["week", "month", "year"]),
        ],
        request=_FILTER_BODY,
    )
    def post(self, request):
        top = request.query_params.get("top", "user")
        if top not in self.CONFIG:
            return self.bad_request("top must be 'user', 'country' or 'blog'.")

        try:
            range_name = resolve_range(request.query_params.get("range"))
            tree = self.filter_tree(request)
            views = apply_filters(BlogView.objects.all(), tree, "view")
        except (ValueError, FilterError) as exc:
            return self.bad_request(str(exc))

        views = views.filter(viewed_at__gte=window_start(range_name))
        config = self.CONFIG[top]
        group_field = config["group"]

        # Pull the author alongside the title for the blog case so y is useful.
        value_fields = [group_field]
        if "extra" in config:
            value_fields.append(config["extra"])

        rows = (
            views.values(*value_fields)
            .annotate(
                number_of_blogs=Count("blog", distinct=True),
                total_views=Count("id"),
            )
            .order_by("-total_views")[:10]
        )

        data = [
            {
                "x": row[group_field],
                "y": row[config["extra"]] if "extra" in config else row["number_of_blogs"],
                "z": row["total_views"],
            }
            for row in rows
        ]
        return Response({"top": top, "range": range_name, "data": data})


class PerformanceAnalytics(_AnalyticsView):
    """API #3 - time-series performance for one user or everyone."""

    @extend_schema(
        summary="Time-series performance for one user or everyone",
        parameters=[
            OpenApiParameter("compare", str, enum=["day", "week", "month", "year"]),
            OpenApiParameter("user_id", int, description="Omit for all users."),
        ],
        request=_FILTER_BODY,
    )
    def post(self, request):
        try:
            compare = resolve_range(request.query_params.get("compare"))
            tree = self.filter_tree(request)
        except (ValueError, FilterError) as exc:
            return self.bad_request(str(exc))

        user_id = request.query_params.get("user_id")
        trunc = TRUNC_FUNCS[compare]
        # Performance shows several periods of history, not a single window.
        start = series_start(compare)

        try:
            blogs = apply_filters(Blog.objects.all(), tree, "blog")
            views = BlogView.objects.all()
            if user_id:
                blogs = blogs.filter(author_id=user_id)
                views = views.filter(blog__author_id=user_id)
        except (ValueError, FilterError) as exc:
            return self.bad_request(str(exc))

        # Two grouped queries (blogs created, views received) keyed by period,
        # then stitched together in Python. Avoids per-period queries entirely.
        blogs_by_period = {
            r["period"]: r["n"]
            for r in blogs.filter(created_at__gte=start)
            .annotate(period=trunc("created_at"))
            .values("period")
            .annotate(n=Count("id"))
        }
        views_by_period = {
            r["period"]: r["n"]
            for r in views.filter(viewed_at__gte=start)
            .annotate(period=trunc("viewed_at"))
            .values("period")
            .annotate(n=Count("id"))
        }

        periods = sorted(set(blogs_by_period) | set(views_by_period))
        data = []
        previous_views = None
        for period in periods:
            blog_count = blogs_by_period.get(period, 0)
            view_count = views_by_period.get(period, 0)
            data.append(
                {
                    "x": {
                        "period": period.date().isoformat(),
                        "number_of_blogs": blog_count,
                    },
                    "y": view_count,
                    "z": growth_pct(view_count, previous_views),
                }
            )
            previous_views = view_count

        scope = f"user:{user_id}" if user_id else "all"
        return Response({"scope": scope, "compare": compare, "data": data})
