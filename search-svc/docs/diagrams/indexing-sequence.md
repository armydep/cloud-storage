# Indexing Sequence

How a file reaches the search index, and how it leaves. Everything below the
dividing line happens after the user's request has returned, so upload latency is
unaffected.

**Live.** Delivered by #133. The `search-indexer` compose service runs the
`search-svc` image with `command: python -m app.indexer`, and writes to the
`files-v1` index through the `files` alias.

## Upload

```mermaid
sequenceDiagram
    participant Browser
    participant API as Backend API
    participant S3 as S3 / MinIO
    participant DB as PostgreSQL
    participant Relay as Notification Relay
    participant MQ as RabbitMQ
    participant Indexer as search-svc indexer
    participant ES as Elasticsearch

    Browser->>API: POST /files/presign-upload
    API-->>Browser: presigned URL
    Browser->>S3: PUT bytes
    Note over Browser,S3: file bytes never pass through the API

    Browser->>API: POST /files/complete-upload
    API->>S3: verify checksum
    API->>DB: BEGIN
    API->>DB: INSERT files row
    API->>DB: INSERT notification_outbox (file_created)
    API->>DB: COMMIT both together
    API-->>Browser: 200 StoredFilePublic

    Note over Browser,ES: the user's upload is complete here

    loop Poll unpublished rows
        Relay->>DB: SELECT FOR UPDATE SKIP LOCKED
        Relay->>MQ: publish file_created
        MQ-->>Relay: publisher confirm
        Relay->>DB: set published_at
    end

    MQ->>Indexer: deliver from q.search
    Indexer->>ES: index document, _id = file id
    Indexer->>MQ: ack
```

The backend change is **one extra INSERT** inside a transaction that already
exists. If Elasticsearch is down when the indexer runs, the message stays queued
and is retried; the upload still succeeded.

## Delete

```mermaid
sequenceDiagram
    participant Browser
    participant API as Backend API
    participant DB as PostgreSQL
    participant MQ as RabbitMQ
    participant Indexer as search-svc indexer
    participant ES as Elasticsearch

    alt Single file
        Browser->>API: DELETE /files/{id}
        API->>DB: delete row + INSERT outbox (file_deleted), one transaction
        MQ->>Indexer: file_deleted
        Indexer->>ES: delete document by _id
        Note over Indexer,ES: "not found" counts as success —<br/>otherwise a duplicate delivery loops until it dead-letters
    else Whole folder
        Browser->>API: DELETE /files/folders/{id}
        API->>DB: delete subtree + INSERT outbox (folder_deleted), one transaction
        Note over API,DB: ONE event for the subtree, not one per descendant
        MQ->>Indexer: folder_deleted
        Indexer->>ES: delete_by_query on owner_id + folder_path prefix
        Note over Indexer,ES: expanded server-side, so cost does not<br/>scale with the number of events published
    end
```

## Guarantees

```
file mutation → outbox     ATOMIC          same transaction
outbox → broker            at-least-once   relay may republish after a crash
broker → indexer           at-least-once   ack-based redelivery
──────────────────────────────────────────────────────────────
end to end                 at-least-once
```

The indexer must therefore tolerate seeing any event twice. Indexing by file id
is naturally idempotent; deletes must treat a missing document as success.

A *lost* event is a different matter. `search-svc` cannot detect divergence,
because it never reads PostgreSQL — so recovery is always backend-driven, by
replaying events. That is also how the backfill of pre-existing files works
(**planned, #134**): `backend` replays `file_created` for every existing file
through this same path, rather than `search-svc` reaching into the database.

## Index creation

The index is created on first write through `ensure_index`, always via the
`files` alias rather than the concrete `files-v1` name, so a future mapping
change can reindex into `files-v2` and swap the alias without downtime.

`number_of_replicas` is set to `0` deliberately. A single-node cluster can never
satisfy a positive replica count, so leaving the default would block every index
creation for around thirty seconds waiting on shard allocation that cannot
succeed.
