# Search Query Sequence

How a search request travels from the client to a result set. Traefik selects the
service by path prefix; `search-svc` verifies the token locally and never calls
`backend` or PostgreSQL.

**Live.** The Elasticsearch steps below are implemented (#134).

```mermaid
sequenceDiagram
    participant Client
    participant Traefik
    participant Svc as search-svc
    participant ES as Elasticsearch
    participant API as Backend API

    Client->>Traefik: GET /api/v1/search/files?folder_path=root.docs&q=report
    Note over Traefik: PathPrefix(/api/v1/search) at priority 100<br/>wins over the backend catch-all
    Traefik->>Svc: forward request

    Svc->>Svc: verify JWT with shared SECRET_KEY (HS256)
    alt Token missing
        Svc-->>Client: 401
    else Token invalid or no sub claim
        Svc-->>Client: 403
    else Token valid
        Svc->>Svc: read user id from sub

        Svc->>Svc: validate folder_path against ltree pattern
        alt folder_path missing or malformed
            Svc-->>Client: 422
        else folder_path valid
            Svc->>ES: query — match name, FILTER owner_id + folder_path prefix
            Note over Svc,ES: owner_id is applied at a single chokepoint,<br/>in filter context, independently of folder_path
            alt Elasticsearch unavailable
                ES-->>Svc: connection error
                Svc-->>Client: 503
            else Results returned
                ES-->>Svc: hits with sort values
                Svc->>Svc: map hits, encode last sort value as opaque cursor
                Svc-->>Client: 200 results and next_cursor
            end
        end
    end

    Note over Client,API: Acting on a result goes back to backend
    Client->>API: POST /api/v1/files/{id}/presign-download
    Note over Svc: search-svc is not involved — it is read-only<br/>and never on a write path
```

## The shape to notice

**Search finds, backend serves.** A search result is an id plus display metadata.
The moment the user acts on one — download, share, delete — traffic returns to
`backend` through the normal path.

The security-critical line is the `owner_id` filter. A search endpoint returns a
*list*, so one missing filter leaks many records at once rather than one. It is
applied in filter context, at a single place every query routes through, and
independently of `folder_path` — passing another user's folder path returns
nothing rather than their files.
