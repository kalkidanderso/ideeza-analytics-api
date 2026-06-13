"""Dynamic multi-table filter engine.

Clients send a small JSON tree describing how to filter the queryset, e.g.

    {
        "and": [
            {"eq": {"field": "author__country__code", "value": "US"}},
            {"not": {"eq": {"field": "title", "value": "draft"}}}
        ]
    }

We walk that tree and turn it into a single Django Q object, so the whole
thing resolves in one query instead of chained Python-side filtering.
"""
import operator
from functools import reduce

from django.db.models import Q

# Field names a request is allowed to reference, per logical resource.
# Anything outside this list is rejected so callers can't probe the schema.
ALLOWED_FIELDS = {
    "blog": {
        "title",
        "author__username",
        "author__country__code",
        "author__country__name",
        "created_at",
    },
    "view": {
        "blog__title",
        "blog__author__username",
        "blog__author__country__code",
        "blog__author__country__name",
        "viewed_at",
    },
}


class FilterError(ValueError):
    """Raised when a filter tree is malformed or references a bad field."""


def build_q(node, allowed):
    """Recursively turn a filter node into a Q object."""
    if not isinstance(node, dict) or len(node) != 1:
        raise FilterError("Each filter node needs exactly one operator key.")

    op, payload = next(iter(node.items()))

    if op == "and":
        return _combine(payload, allowed, Q.AND)
    if op == "or":
        return _combine(payload, allowed, Q.OR)
    if op == "not":
        return ~build_q(payload, allowed)
    if op == "eq":
        return _equals(payload, allowed)

    raise FilterError(f"Unsupported operator: {op!r}")


def _combine(children, allowed, connector):
    if not isinstance(children, list) or not children:
        raise FilterError("and/or expects a non-empty list of conditions.")
    # Q & / Q | return new objects, so fold the children left to right with
    # the public operators rather than mutating in place.
    op = operator.and_ if connector == Q.AND else operator.or_
    return reduce(op, (build_q(child, allowed) for child in children))


def _equals(payload, allowed):
    if not isinstance(payload, dict) or "field" not in payload:
        raise FilterError("eq expects {'field': ..., 'value': ...}.")
    field = payload["field"]
    if field not in allowed:
        raise FilterError(f"Filtering on {field!r} is not allowed.")
    return Q(**{field: payload.get("value")})


def apply_filters(queryset, raw_filter, resource):
    """Apply a (possibly empty) filter tree to a queryset."""
    if not raw_filter:
        return queryset
    allowed = ALLOWED_FIELDS[resource]
    return queryset.filter(build_q(raw_filter, allowed))
