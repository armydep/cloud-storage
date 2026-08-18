# search-svc documentation

Reference documentation for the search service. These documents describe the
service as it is **built** and as it is **contracted**.

The authoritative design record — the numbered decisions and their reasoning —
lives in [`docs/phases/phase-10-search-service.md`](../../docs/phases/phase-10-search-service.md)
at the repository root. Where these documents and the phase document disagree,
the phase document is correct and this folder needs updating.

## Contents

| Document | Covers |
| --- | --- |
| [architecture.md](architecture.md) | What the service owns, what it must never touch, and how requests reach it |
| [api.md](api.md) | Endpoint reference: parameters, responses, error codes |
| [events.md](events.md) | The broker contract — events consumed, payloads, idempotency |
| [diagrams/search-query-sequence.md](diagrams/search-query-sequence.md) | A query, end to end |
| [diagrams/indexing-sequence.md](diagrams/indexing-sequence.md) | How a file reaches the index |

## Status legend

The service is being delivered in slices. Every section below is marked so that
nothing here reads as implemented when it is not:

| Mark | Meaning |
| --- | --- |
| **Live** | Implemented and running today |
| **Planned (#nnn)** | Contracted and designed, not yet built; the issue tracks it |

At the time of writing:

- **Slice 1 (#132) is live** — Traefik routing, authentication, the request
  contract.
- **Slice 2 (#133) is live** — Elasticsearch, the index mapping and alias, file
  lifecycle events, and the indexer that applies them.
- **Slice 3 (#134) is live** — real query results, keyset pagination, and a
  backend backfill of files that predate the event stream.
- **Slice 4 (#135) is live** — folder-scoped search UI in the web client.

The index is populated, correct, and queryable from the web client. This slice
does not tick `ROADMAP 3.4`; that roadmap item covers work beyond this web UI.
