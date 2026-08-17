# Phase 10: Search service

## Goal

Introduce `search-svc`, a separately deployable service that answers file search
queries from its own Elasticsearch index, fed by events rather than by reading
the application database.

Requests reach it through the existing Traefik ingress: `/api/v1/search/*` routes
to `search-svc`, everything else continues to `backend`.

This phase advances ROADMAP 3.4 (sorting, filtering and search), ROADMAP 8.1
(independently deployable services) and ROADMAP 8.3 (API gateway).

## Product and technical decisions

1. **`search-svc` is a genuinely separate service, unlike the notification
   workers.** Phase 8 decision 9 kept the relay and consumers inside the backend
   package because they wrote to a schema the backend owns. Search is the
   opposite case: it owns a different datastore, needs none of the Postgres
   schema, and is fed by events. Separation is warranted here.

2. **`search-svc` never reads PostgreSQL.** It is given no database credentials.
   The index is built exclusively from events consumed off RabbitMQ. This is what
   keeps the split from becoming a distributed monolith, and it is enforced by
   configuration rather than by discipline.

3. **Elasticsearch is the engine, chosen deliberately over lighter options.**
   Meilisearch or Typesense would cover this workload at a fraction of the
   operational cost, and Postgres `tsvector` + `pg_trgm` would need no new
   infrastructure at all. Elasticsearch is chosen anyway. The accepted costs are:
   a JVM with a 1–2 GB memory floor, `vm.max_map_count` tuning on Linux hosts, an
   independent upgrade path, and cluster/shard semantics to operate in
   production. Recorded so the cost is visible rather than discovered later.

4. **Traefik is the API gateway. No new gateway component is introduced.**
   Routing is a label on `search-svc` combining the existing host rule with a
   path prefix and a higher priority than the backend catch-all. ROADMAP 8.3 is
   satisfied by configuration.

5. **`search-svc` validates JWTs itself.** Token verification is stateless HMAC
   (`app/core/security.py`), so it shares `SECRET_KEY` and performs no callback to
   `backend` on the request path. Accepted consequence: a deactivated user keeps
   working search until their token expires, because `is_active` lives in
   Postgres and decision 2 forbids reading it.

6. **Tenant isolation is enforced at one chokepoint.** `owner_id` is a mandatory
   filter on every query, applied in a single place that all endpoints route
   through — never per-endpoint. A search endpoint returns a *list*, so one
   missing filter leaks many records at once rather than one. This is the
   highest-risk part of the phase.

7. **The index is eventually consistent, and this is accepted.** A newly uploaded
   file may not appear in search results for a short window. Documented in the
   API so clients do not treat it as a bug.

   A *lost* event is different from a delayed one: because `search-svc` never
   reads Postgres, it cannot detect that its view has diverged. A dropped
   `file_deleted` leaves a permanently stale entry, and the user clicking it gets
   a 404 from `backend`. Reconciliation is therefore always backend-driven —
   replaying events (decision 8), never `search-svc` comparing against the source
   of truth.

8. **Backfill is done by replaying events from `backend`, not by `search-svc`
   reading the database.** Existing files predate the event stream. The backfill
   is a backend command that emits `file_created` for every existing file through
   the normal outbox path, preserving decision 2.

9. **Elasticsearch has no ingress.** It is reachable only on the internal compose
   network by `search-svc`. It is never exposed through Traefik, and its port is
   not published to the host in production.

10. **The index is addressed through an alias.** `files` is an alias pointing at
    `files-v1`. Mapping changes are handled by building `files-v2` and swapping
    the alias, so reindexing never requires downtime. Doing this from the start
    costs nothing; retrofitting it later requires an outage.

11. **Search is scoped to a folder subtree, not global.** Every query carries a
    `folder_path` and returns matches from that folder *and everything beneath
    it* — the recursive reading, matching how file managers behave and how the
    existing ltree paths already model the hierarchy. There is no whole-workspace
    search. `folder_path` is therefore a **filter**, not merely a display field,
    which raises the cost of it going stale (see decision 12).

    `search-svc` validates the path format itself. It cannot import the backend's
    `LTREE_PATH_PATTERN` (decision 1), so it carries its own copy of the
    validation. An unvalidated path must never reach the query builder.

    The `owner_id` filter still applies first and independently: passing another
    user's folder path returns nothing, because ownership is enforced at the
    chokepoint in decision 6, not by the path.

12. **`folder_path` is a keyword field maintained by a `folder_renamed` event.**
    Renaming a folder invalidates the stored path on every descendant document.
    The indexer applies one `folder_renamed` event with an Elasticsearch
    `update_by_query` against a path prefix — one event, one server-side
    operation, regardless of subtree size. It never fetches and re-pushes
    documents individually.

    This matters more than it would under a global-search design: because of
    decision 11 a stale path means files **disappear from searches of their own
    folder**, not merely display the wrong breadcrumb.

    Rename does not exist yet (ROADMAP 1.2), so no such event is emitted today.
    The mapping is nevertheless chosen now, because changing it later requires a
    reindex.

13. **Deleting a user leaves orphaned documents in the index. Accepted.**
    `files.owner_id` cascade-deletes in Postgres when a user row is removed, and
    a database cascade emits no application event — the rows simply vanish.
    Documents belonging to a deleted user therefore remain in Elasticsearch
    indefinitely.

    The consequence is stated plainly because it is a privacy one, not a tidiness
    one: the index retains personal data (filenames) after the account is gone.
    Accepted deliberately for now. Cleanup, if it is ever needed, is a
    `delete_by_query` on `owner_id`; making it automatic would require a
    `user_deleted` event emitted before the cascade runs.

    This is the same class of gap as the swallowed `delete_object` failures in
    the orphan-cleanup work: a path that bypasses the event stream entirely.

## Architecture

```
                        ┌──────────── Traefik ────────────┐
   client ─────────────►│  Host(api.DOMAIN)               │
                        │    && PathPrefix(/api/v1/search)│──┐
                        │    priority 100                 │  │
                        │                                 │  │
                        │  Host(api.DOMAIN)   (catch-all) │──┼──► backend
                        └─────────────────────────────────┘  │
                                                              ▼
                                                        ┌───────────┐
                                                        │ search-svc│
                                                        └─────┬─────┘
                                                              │ query
                                                              ▼
                                                     ┌─────────────────┐
                                                     │ Elasticsearch   │
                                                     │  alias: files   │
                                                     └────────▲────────┘
                                                              │ index
   backend ──► notification_outbox ──► relay ──► exchange ──► q.search ──► indexer
   (file_created / file_deleted / folder_deleted)
```

The left half already exists from Phase 8. `q.search` is one more binding on the
same exchange, and the indexer is one more consumer — the same shape as the email
and in-app consumers.

## API outline

```
GET  /api/v1/search/files
       ?folder_path=<ltree path>     (required — see decision 11)
       &q=<text>
       &category=<image|document|...>
       &limit=<1..100>
       &cursor=<opaque>
     → 200 { "results": [...], "next_cursor": "..." | null }

GET  /api/v1/search/health
     → 200 { "status": "ok", "index": "files", "engine": "elasticsearch" }
```

Every request requires a bearer token. Results contain only files owned by the
caller, from the given folder and its descendants. Query constraints are declared
so they appear in the OpenAPI schema.

A malformed `folder_path` is rejected with 422 before it reaches the query
builder, mirroring the backend's rule that an unvalidated ltree path must never
reach the datastore.

Pagination is keyset, using Elasticsearch `search_after` behind an opaque cursor.
Not offset — `from`/`size` degrades deep into result sets, and SCALE 4.3 already
records that lesson for this project.

## Index model

```
alias: files  ──►  index: files-v1

  _id          file uuid
  owner_id     keyword      ← mandatory filter, filter context (cacheable, unscored)
  name         text         ← analyzed for search
  name.raw     keyword      ← exact match and sorting
  folder_path  keyword
  mime_type    keyword
  category     keyword
  size_bytes   long
  created_at   date
```

Filename analysis needs deliberate choice: the standard analyzer splits
`report_2024-final.pdf` in ways that surprise users, and prefix matching needs
either `edge_ngram` or a `search_as_you_type` field. This is a slice-2 decision,
not an implementation detail.

## Slice breakdown

### Slice 1 — service skeleton and gateway routing

A `search-svc` FastAPI service with JWT validation, the endpoints above returning
**correctly shaped empty results**, a compose service, and the Traefik routing
label. No Elasticsearch yet.

Ships the routing and the contract. Nothing returns fabricated data.

### Slice 2 — Elasticsearch, index model, and the indexer

An `elasticsearch` compose service; the index mapping and alias; `file_created`,
`file_deleted` and `folder_deleted` events emitted by `backend` into the existing
outbox; a `q.search` binding; an indexer consumer in `search-svc` that applies
them.

### Slice 3 — real queries and backfill

Replace the empty results with real Elasticsearch queries behind the single
ownership chokepoint, plus a backend backfill command that replays
`file_created` for every existing file.

### Slice 4 — search UI in the React SPA

The front end for ROADMAP 3.4.

## Acceptance flow

1. A signed-in user calls `GET /api/v1/search/files?q=report`.
2. Traefik matches the path prefix and routes to `search-svc`, not `backend`.
3. `search-svc` validates the JWT locally and extracts the user id.
4. It queries Elasticsearch with `owner_id` applied as a mandatory filter.
5. Results contain only that user's files, paginated by opaque cursor.
6. A file uploaded moments earlier appears once the indexer has consumed its
   event.
7. A second user issuing the same query never sees the first user's files.

## Out of scope

- Searching inside file *contents*. This phase indexes metadata only.
- Searching files shared with the user — see open questions.
- Folder search.
- Elasticsearch clustering, replicas, or snapshot/restore. Single node for now.
- Migrating any existing backend endpoint behind the gateway. Only the new
  `/api/v1/search` prefix is routed to `search-svc`.

## Open questions

1. **Filename analysis strategy.** Standard analyzer, custom analyzer, or
   `search_as_you_type`. Affects the mapping, so it must be settled in slice 2
   before any index is populated.

2. **What happens to search when Elasticsearch is down?** Return 503, or degrade
   to an empty result set. 503 is more honest; empty results are friendlier and
   look identical to "no matches", which may hide an outage.

3. **Ranking: relevance or recency?** Elasticsearch defaults to relevance. For a
   file store, a user searching a half-remembered filename often wants the most
   recent match. Decide in slice 3.

4. **Does `q.search` get a dead-letter exchange?** `q.email` has one from Phase 8.
   If the indexer is down for an extended period, messages accumulate. Consistency
   one way or the other is worth choosing deliberately.

5. **Does `search-svc` get Prometheus metrics?** `backend` gained them in the
   observability work; leaving the new service unobserved is a gap, but adding
   them is not free.

Resolved during design, retained for context:

- **Owned files only, not shared files.** Decision 11 scopes search to a folder
  subtree, and files shared with a user do not live in that user's folder tree —
  so folder-scoped search excludes them naturally. Revisit if a "search shared
  with me" requirement appears; it would need the index to model the share graph
  and track grants and revocations.
