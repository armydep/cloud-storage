# Events

**Live.** Event emission, the `q.search` binding and the indexer were delivered
by #133.

## How the index is fed

`search-svc` never reads PostgreSQL. The index is built exclusively from events
that `backend` publishes through the notification infrastructure built in
phase 8.

```
backend                        RabbitMQ                    search-svc
───────                        ────────                    ──────────
file mutation
  └─ INSERT notification_outbox
       (same transaction)
                ↓
              relay ──publish──► exchange: notifications
                                      │  routing key = event_type
                                      ├─► q.email
                                      ├─► q.inapp
                                      └─► q.search ──────► indexer ──► Elasticsearch
```

Adding search as a consumer required no change to the outbox, the relay, or the
existing consumers. That is the point of fanning out at the broker rather than at
enqueue time (phase 8 decision 4).

## Topology

| | Value |
| --- | --- |
| Exchange | `notifications` (topic, durable) |
| Queue | `q.search` (durable) |
| Dead-letter exchange | `notifications.dead-letter.search` |
| Dead-letter queue | `q.search.dead-letter` |
| Delivery limit | 5 |
| Routing keys | `file_created`, `file_deleted`, `folder_deleted` |

Constants live in `search-svc/app/broker.py` and, independently, in
`backend/app/notifications/broker.py`.

**The two declarations must agree exactly.** Both sides declare `q.search` with
the same arguments; a mismatch makes RabbitMQ reject one side's declaration with
`PRECONDITION_FAILED`. Changing a queue argument means changing it in both
places, in the same release.

### Who declares the queue

**`backend` declares `q.search`**, in `declare_topology`, even though it never
consumes it.

The reason is a silent failure mode: a topic exchange **discards** a message that
matches no binding, with no error anywhere. If `search-svc` declared the queue
only from its own side — the more conventional AMQP arrangement — every file
event published before the indexer first started would vanish, and nothing would
report it. Declaring on the publishing side closes that window.

This does not weaken the no-shared-code rule. What crosses the boundary is a set
of strings agreed in the phase document, not a code dependency: `backend` imports
nothing from `search-svc`, and `search-svc` carries its own AMQP client and its
own copies of these constants.

## Events consumed

| Event | Emitted by | Indexer action |
| --- | --- | --- |
| `file_created` | `complete_upload` | Index a document, keyed by file id |
| `file_deleted` | `delete_file` | Delete the document by file id |
| `folder_deleted` | `delete_folder` | `delete_by_query` on `owner_id` + `folder_path` prefix |

### Payloads

`file_created` carries everything the index needs. The index is fully
denormalized, so the indexer never needs a second lookup:

```
file_id, owner_id, name, folder_path, mime_type, category, size_bytes, created_at
```

`file_deleted` carries `file_id` and `owner_id`.

`folder_deleted` carries `owner_id` and the deleted folder's `folder_path`.

Emission happens inside the transaction that already exists for each mutation —
`session.add` plus `session.flush()`, no commit — so the event and the mutation
commit together or not at all. The backend test suite covers this directly, with
per-mutation tests proving that a notification failure rolls the mutation back.

### One event per folder delete

`folder_deleted` is a **single** event covering the whole subtree, not one event
per descendant file. The indexer expands it server-side with `delete_by_query`.

Emitting per-file events would produce a burst proportional to subtree size —
the unbounded-subtree-write problem from the scalability review, copied into the
event stream.

## Events that do not exist

There is no `file_renamed` or `folder_renamed`, because rename is not
implemented — ROADMAP 1.2 and 1.3 are both open and there is no rename route in
`backend/app/api/routes/files.py`.

The mapping is nevertheless chosen with rename in mind. When it lands, a folder
rename must be applied as one `folder_renamed` event handled with an
Elasticsearch `update_by_query` against a path prefix, never a per-document
rewrite.

This matters more than it looks: because search *filters* on `folder_path`, a
stale value makes files **disappear from searches of their own folder**, not
merely display a wrong breadcrumb. Whoever implements rename has to remember to
emit the event — nothing enforces it.

## Idempotency

Delivery is at-least-once end to end. The relay can republish after a crash, so
the indexer **will** see the same event twice.

| Operation | Why it is safe |
| --- | --- |
| Index by document `_id` | Naturally idempotent — the file id is the `_id`, so a repeat overwrites identically |
| Delete by `_id` | A 404 from Elasticsearch is treated as success |
| `delete_by_query` | Naturally idempotent — the second run matches nothing |

The 404-as-success rule is not a nicety. If a delete of an already-deleted
document raised, the message would be redelivered until it dead-lettered, turning
a routine duplicate into an alert.

`backend/app/notifications/broker.py` passes a `message_id` to handlers — the
outbox row id, used by the in-app consumer against a unique constraint. The
indexer does not need it, because indexing by file id is already idempotent, but
it stays in the handler signature.

## The indexer process

`search-indexer` is a separate compose service running the same image as
`search-svc` with `command: python -m app.indexer`. It depends on both
`elasticsearch` and `rabbitmq` reporting healthy.

Elasticsearch access is defined by `ELASTICSEARCH_URL` and needs no credentials:
the cluster has no ingress and is reachable only on the internal compose network,
in the same way `POSTGRES_SERVER=db` already works for the backend.

Index writes go through a `SearchIndex` protocol (`search-svc/app/es_index.py`),
with `ElasticsearchIndex` as the only implementation. The protocol exists so the
indexer's event-handling logic is unit-testable without a live cluster; the
integration path is covered separately by a testcontainer.
