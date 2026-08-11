# Detailed File Download Sequence

This diagram documents the implemented presigned-download flow. The application
does not currently have an access-log table or a download-count column, so no
download logging `INSERT` or counter `UPDATE` occurs.

```mermaid
sequenceDiagram
    participant User
    participant Frontend
    participant API
    participant Users as user table
    participant Files as files table
    participant Shares as file_shares table
    participant Blobs as file_blobs table
    participant AccessLog as access log table, not implemented
    participant Storage as S3 object storage

    User->>Frontend: Click Download
    Frontend->>API: POST files/file_id/presign-download

    API->>Users: BEGIN transaction and SELECT user WHERE id = jwt subject
    alt Token invalid, user missing, or user inactive
        API-->>Frontend: Authentication error
        Note over API,Users: Read transaction closes without COMMIT
    else Active user
        Users-->>API: User id and active status
        API->>Files: SELECT files LEFT JOIN file_shares ON file_id
        Note over Files,Shares: WHERE files.id = file_id AND owner_id = user_id OR recipient_id = user_id

        alt File is absent or user has no permission
            Files-->>API: No row
            API-->>Frontend: 404 File not found
            Note over API,Shares: Missing and unauthorized files intentionally have the same response
        else Owner or shared recipient is authorized
            Files-->>API: File id, name, blob_hash, size, and metadata
            Note over API,Blobs: No file_blobs SELECT occurs and key is derived from files.blob_hash
            API->>API: Build sha256/blob_hash key and attachment filename
            API->>Storage: Sign GET URL with expiry and content disposition
            Note over API,Storage: Signing is local and no HEAD or GET occurs yet
            API-->>Frontend: Presigned download URL and expires_in
            Note over API,AccessLog: No access-log INSERT and no download-count UPDATE
            Note over API,Files: Read-only transaction closes without COMMIT
        end
    end

    Frontend->>Storage: GET canonical object with signed URL
    alt URL is valid and object exists
        Storage-->>Frontend: File bytes
        Frontend-->>User: Save or open file
        Note over AccessLog,Storage: S3 success is not reported to the API, so no DB logging occurs
    else URL expired, signature invalid, or object missing
        Storage-->>Frontend: S3 error
        Frontend-->>User: Show download failure
    end
```

## Requested-operation mapping

| Requested operation | Current implementation |
| --- | --- |
| Metadata existence | Authorized lookup in `files` |
| Permission | `files.owner_id` or matching `file_shares.recipient_id` |
| Physical existence | Determined by the direct S3 `GET`; the API does not call `HEAD` |
| Retrieval | Frontend downloads through a presigned S3 URL; the API does not stream bytes |
| Access log / download count | Not implemented; no table or counter participates |
