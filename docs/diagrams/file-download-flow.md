# File Download Flow

This diagram shows the download flow using presigned URLs. The backend authorizes access with a
single query; the browser then downloads file bytes directly from MinIO. Presigned URL generation is
local HMAC signing — it never makes a network call to MinIO.

Two Postgres tables are involved:

| Table | Role |
| --- | --- |
| `files` | The file's metadata row, including `owner_id` and `blob_hash` |
| `file_shares` | Grants a non-owner recipient access to someone else's file |

Both are read in one query — `get_downloadable_file_by_id` outer-joins `files` to `file_shares` so a
caller who is either the owner or a share recipient resolves the file in a single round trip; anyone
else gets no row, which the route maps to 404, never 403.

## Full flow

```mermaid
sequenceDiagram
    participant User
    participant Frontend
    participant Backend as "Backend API"
    participant files as "files"
    participant file_shares as "file_shares"
    participant MinIO

    User->>Frontend: Click file download
    Frontend->>Backend: POST /files/{file_id}/presign-download

    Backend->>files: SELECT files LEFT JOIN file_shares<br/>WHERE files.id = file_id<br/>AND (files.owner_id = user_id OR file_shares.recipient_id = user_id)
    files-->>Backend: row (as owner) or none
    file_shares-->>Backend: row (as recipient) or none

    alt No matching row (not owner, not a share recipient, or file does not exist)
        Backend-->>Frontend: 404 File not found
    else Caller is the owner or a share recipient
        Backend->>Backend: Derive object_key = sha256/{files.blob_hash}
        Backend->>Backend: Sign GET URL (local HMAC — no MinIO call)
        Backend-->>Frontend: download_url, method=GET, expires_in
    end

    Frontend->>MinIO: GET download_url
    alt URL expired or object missing
        MinIO-->>Frontend: error
        Frontend-->>User: Show download failure
    else URL valid
        MinIO-->>Frontend: file bytes
        Frontend-->>User: Save or open file
    end
```

## Happy path

```mermaid
sequenceDiagram
    participant User
    participant Frontend
    participant Backend as "Backend API"
    participant files as "files"
    participant file_shares as "file_shares"
    participant MinIO

    User->>Frontend: Click file
    Frontend->>Backend: Request download URL
    Backend->>files: SELECT files LEFT JOIN file_shares WHERE id = file_id<br/>AND (owner_id = user_id OR recipient_id = user_id)
    files-->>Backend: file row (blob_hash, name)
    Backend->>Backend: Build object_key from blob_hash
    Backend->>Backend: Sign presigned GET URL
    Backend-->>Frontend: download_url
    Frontend->>MinIO: GET download_url
    MinIO-->>Frontend: file bytes
    Frontend-->>User: Save or open file
```

## Ownership vs. share access

`file_shares` is only consulted when the caller is not the file's owner. Both paths return the exact
same 200 response shape — the recipient cannot tell from the API whether they were granted access or
own the file outright.

```mermaid
sequenceDiagram
    participant Owner as "User (owner)"
    participant Recipient as "User (share recipient)"
    participant Backend as "Backend API"
    participant files as "files"
    participant file_shares as "file_shares"

    Owner->>Backend: POST /files/{file_id}/presign-download
    Backend->>files: SELECT ... WHERE files.owner_id = owner.id
    files-->>Backend: row matches on owner_id
    Backend-->>Owner: download_url

    Recipient->>Backend: POST /files/{file_id}/presign-download
    Backend->>files: SELECT ... WHERE files.owner_id = recipient.id
    files-->>Backend: no match (recipient does not own it)
    Backend->>file_shares: (same query) WHERE file_shares.recipient_id = recipient.id
    file_shares-->>Backend: row matches on recipient_id
    Backend-->>Recipient: download_url
```
