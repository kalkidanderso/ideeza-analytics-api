# IDEEZA Analytics Service

A small Django REST service exposing three analytics endpoints over a
blog/views dataset. All three share a single dynamic filter engine and a
common set of time-series aggregation helpers, and every query is resolved
at the database level to avoid N+1 problems.

## Data model

`Country -> User -> Blog -> BlogView`. Each view is stored as its own row
(`BlogView.viewed_at`), which lets us aggregate over any time range without
storing pre-computed counters.

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed        # optional sample data
python manage.py runserver
```

## Tests

```bash
python manage.py test
```

The suite covers the filter engine (operators + field allow-list), the
aggregation helpers, and all three endpoints end to end. CI runs the same
command on every push (see `.gitlab-ci.yml`).

## Endpoints

All endpoints accept `POST` so the dynamic filter tree can travel in the
body. Query params control grouping and time range.

### 1. `POST /analytics/blog-views/`

Groups blogs and views by `object_type` (`country` or `user`).

| param | values | meaning |
|-------|--------|---------|
| `object_type` | `country` \| `user` | grouping key |
| `range` | `week` \| `month` \| `year` | single time window (e.g. last month) |
| `limit` | int (1-1000, default 100) | max rows returned |

Output rows: `x` = grouping key, `y` = number_of_blogs, `z` = total_views.

### 2. `POST /analytics/top/`

Top 10 by total views.

| param | values |
|-------|--------|
| `top` | `user` \| `country` \| `blog` |
| `range` | `week` \| `month` \| `year` |

Output rows vary by `top` type, as the spec requires:

- `user` / `country`: `x` = entity, `y` = number_of_blogs, `z` = total_views.
- `blog`: `x` = blog title, `y` = author, `z` = total_views (blog count is
  always 1 here, so the author is the useful second dimension).

### 3. `POST /analytics/performance/`

Time-series performance for one user or everyone.

| param | values |
|-------|--------|
| `compare` | `day` \| `week` \| `month` \| `year` |
| `user_id` | optional; omit for all users |

`compare` controls both the period size and the look-back: performance
returns several periods of history (default 12) so growth can be compared
period over period. This differs from `blog-views`/`top`, where `range` is a
single window.

Output rows: `x` = `{period, number_of_blogs}`, `y` = views in the period,
`z` = growth/decline % vs the previous period (`null` for the first period).

## API docs

Once the server is running, open **http://127.0.0.1:8000/docs/** for the
interactive Swagger UI. The raw OpenAPI schema is available at `/schema/`.

## Dynamic filters

Every endpoint accepts an optional `filters` tree in the request body built
from `and` / `or` / `not` / `eq`:

```json
{
  "filters": {
    "and": [
      {"eq": {"field": "blog__author__country__code", "value": "US"}},
      {"not": {"eq": {"field": "blog__title", "value": "Blog 1"}}}
    ]
  }
}
```

The tree is compiled into a single Django `Q` object, so filtering happens
in one query. Only an allow-listed set of fields can be referenced.

## Example

```bash
curl -X POST "http://localhost:8000/analytics/top/?top=country&range=year" \
  -H "Content-Type: application/json" \
  -d '{"filters": {"eq": {"field": "blog__author__country__code", "value": "US"}}}'
```
