# API

Base prefix: `/api/v1/search`

OpenAPI schema: `/api/v1/search/openapi.json`
Interactive docs: `/api/v1/search/docs`

## Authentication

**Live.** Every endpoint requires a bearer token — including `/health`.

Tokens are the ones `backend` issues. `search-svc` verifies them locally with the
shared `SECRET_KEY` and `HS256`, reading the user id from the `sub` claim. There
is no call to `backend` and no database lookup.

| Condition | Response |
| --- | --- |
| Valid token | 200 |
| Missing token | 401 |
| Malformed, expired, or wrongly-signed token | 403 |
| Valid signature but no `sub` claim | 403 |

403 rather than 401 for a bad token mirrors `backend`'s own `get_current_user`
(`app/api/deps.py`), so both services answer identically.

One accepted consequence of local verification: because `is_active` lives in
PostgreSQL and this service never reads it, a **deactivated user keeps working
search until their token expires**. See phase document decision 5.

## `GET /api/v1/search/files`

Searches the caller's files within a folder subtree.

### Parameters

| Name | Type | Required | Constraints | Notes |
| --- | --- | --- | --- | --- |
| `folder_path` | string | **yes** | 1–1024 chars, ltree pattern | The folder to search. Results include its descendants. |
| `q` | string | no | — | Free text matched against the filename |
| `category` | enum | no | see below | Filter by file category |
| `limit` | integer | no | 1–100, default 50 | Page size |
| `cursor` | string | no | opaque | Continues a previous page |

`category` accepts: `image`, `video`, `audio`, `document`, `spreadsheet`,
`archive`, `other`.

### Scope

**`folder_path` is required.** There is no whole-workspace search — every query
is scoped to a folder and everything beneath it. Omitting the parameter is a
validation error, not a global search. See phase document decision 11.

Results contain only files owned by the caller. Ownership is applied as a
mandatory filter at a single chokepoint, independently of `folder_path`, so
passing another user's folder path returns nothing rather than their files.

### Response

```json
{
  "results": [
    {
      "id": "b3f1c2a4-...",
      "name": "report_2024.pdf",
      "folder_path": "root.reports",
      "mime_type": "application/pdf",
      "category": "document",
      "size_bytes": 123456,
      "created_at": "2026-08-17T12:00:00Z"
    }
  ],
  "next_cursor": "eyJ..."
}
```

`next_cursor` is `null` on the last page. It is opaque: clients must pass it back
unmodified and must not construct or parse one — it encodes only Elasticsearch
sort values, never `owner_id` or anything else that could change *whose*
results a page returns. See phase document constraint 5.

**Live:** real matches from Elasticsearch, ranked, paginated. `owner_id` is
applied as a mandatory filter at a single chokepoint every query routes
through — independently of `folder_path` — so passing another user's folder
path returns nothing rather than their files.

### Errors

| Status | When |
| --- | --- |
| 401 | No bearer token |
| 403 | Token invalid, expired, or wrongly signed |
| 422 | `folder_path` missing, malformed, or failing the ltree pattern; `limit` out of range; `cursor` malformed or untrusted |
| 503 | Elasticsearch unavailable |

A malformed `folder_path` is rejected at the request boundary, before reaching
any query builder. This mirrors the backend rule that an unvalidated ltree path
must never reach the datastore, where it surfaces as a 500 rather than a 422.
A cursor that fails to decode, or whose shape doesn't match a sort-value
triple, is rejected the same way — it never reaches Elasticsearch.

On 503 rather than empty results when the search engine is down: an empty result
set is indistinguishable from "no matches" and would hide an outage from users
and operators alike. See phase document decision 15.

### Pagination

**Live.** Keyset pagination using Elasticsearch `search_after` behind the
opaque cursor. Not offset — `from`/`size` degrades deep into result sets.

The sort is `_score desc, created_at desc, doc_id asc` — `doc_id` is a mapped
field that mirrors the document's Elasticsearch `_id` (the file id) purely so
it can be used as a sort tiebreaker; Elasticsearch disables fielddata on the
real `_id` field by default, so sorting on it directly is rejected. The
tiebreaker is not stylistic: `search_after` requires a deterministic total
ordering, so a unique tiebreaker is needed regardless of ranking preference.
Without it, pagination silently duplicates or skips results whenever scores
tie.

## `GET /api/v1/search/health`

**Live.** Requires authentication.

```json
{
  "status": "ok",
  "index": "files",
  "engine": "elasticsearch"
}
```

Reports live cluster reachability via a lightweight ping — 200 with the body
above when Elasticsearch answers, 503 when it doesn't. Alongside the same 503
behaviour as `GET /files` when the search engine is down.

## Client generation

**Planned (#135).** `scripts/generate-client.sh` generates `frontend/src/client/`
from the backend's OpenAPI schema alone. This service publishes a second schema,
so either the script generates a second client or the schemas are merged. Until
that is decided, the SPA has no generated bindings for these endpoints — and
`frontend/src/client/` must not be hand-edited to add them.
