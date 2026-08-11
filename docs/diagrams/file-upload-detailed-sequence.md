# Detailed File Upload Sequence

This diagram documents the upload flow as currently implemented. Table names
match the production schema. The application does not have `files_metadata`,
`storage_usage`, a quota table, or a file status column. The temporary state is
represented by `pending_uploads`; the durable `files` row is inserted only after
the object has been verified.

```mermaid
sequenceDiagram
    participant User
    participant Frontend
    participant API
    participant Users as user table
    participant Folders as folders table
    participant Pending as pending_uploads table
    participant Blobs as file_blobs table
    participant Claims as file_blob_claims table
    participant Files as files table
    participant Storage as S3 object storage

    User->>Frontend: Select file and folder
    Frontend->>Frontend: Compute SHA-256 and size
    Frontend->>API: POST files/presign-upload

    API->>Users: BEGIN transaction and SELECT user WHERE id = jwt subject
    Users-->>API: Active user
    Note over API,Pending: No quota table exists, so no quota SELECT or UPDATE occurs
    API->>Folders: SELECT folders WHERE owner_id and path match
    Folders-->>API: Target folder
    API->>Blobs: SELECT file_blobs WHERE blob_hash matches
    API->>Claims: SELECT claim WHERE owner_id and blob_hash match

    alt Blob exists and user already has a claim
        API-->>Frontend: upload_required false and canonical object_key
        Note over API,Claims: Read-only transaction closes without COMMIT
    else Upload proof is required
        API->>API: Generate upload_id and temporary object_key
        API->>Storage: Sign PUT URL with MIME type and SHA-256 checksum
        Note over API,Storage: Signing is local and no object is created yet
        API->>Pending: INSERT id, owner_id, blob_hash, object_key, size_bytes, mime_type, created_at, expires_at
        API->>Pending: COMMIT
        API-->>Frontend: Presigned PUT URL and required headers
        Frontend->>Storage: PUT temporary object bytes and checksum
        Storage-->>Frontend: Upload result
    end

    Frontend->>API: POST files/complete-upload
    API->>Users: BEGIN transaction and SELECT user WHERE id = jwt subject
    Users-->>API: Active user
    API->>Folders: SELECT folders WHERE owner_id and path match
    API->>Files: SELECT files WHERE folder_id and name match
    API->>Blobs: SELECT file_blobs WHERE blob_hash matches
    API->>Claims: SELECT claim WHERE owner_id and blob_hash match

    alt Existing blob and existing claim
        API->>Blobs: SELECT file_blobs WHERE blob_hash matches FOR UPDATE
        API->>Blobs: UPDATE file_blobs SET ref_count = ref_count + 1
        API->>Files: INSERT id, owner_id, folder_id, name, mime_type, category, blob_hash, size_bytes, created_at
        API->>Files: COMMIT file row and ref_count update
        API-->>Frontend: StoredFilePublic
    else Pending upload must prove possession
        API->>Pending: SELECT latest unexpired row WHERE owner_id and blob_hash match
        API->>Storage: HEAD temporary object with checksum enabled
        Storage-->>API: Size, MIME type, and SHA-256 checksum

        alt Pending row or object is missing, expired, or invalid
            API->>Pending: ROLLBACK
            API-->>Frontend: 400 upload validation error
        else Temporary object is valid
            opt Canonical blob does not exist
                API->>Storage: COPY temporary object to sha256/blob_hash
                Storage-->>API: Canonical object created
                API->>Blobs: INSERT blob_hash, object_key, size_bytes, ref_count zero, created_at
            end
            API->>Blobs: SELECT file_blobs WHERE blob_hash matches FOR UPDATE
            API->>Claims: SELECT claim WHERE owner_id and blob_hash match
            opt Claim does not exist
                API->>Claims: INSERT id, owner_id, blob_hash, created_at
            end
            API->>Blobs: UPDATE file_blobs SET ref_count = ref_count + 1
            API->>Files: INSERT id, owner_id, folder_id, name, mime_type, category, blob_hash, size_bytes, created_at
            API->>Pending: DELETE pending_uploads WHERE id = upload_id
            API->>Files: COMMIT claim, ref_count, file, and pending deletion
            API->>Storage: DELETE temporary object after DB COMMIT
            API-->>Frontend: StoredFilePublic
        end
    end

    Frontend-->>User: Show uploaded file
```

## Requested-state mapping

| Requested state or operation | Current implementation |
| --- | --- |
| Quota check | Not implemented; there is no quota or `storage_usage` table |
| Initial `PENDING` metadata | `pending_uploads` row and temporary S3 object |
| Final `COMPLETED` metadata | Committed `files` row referencing `file_blobs`; no status field exists |
| Physical upload | Direct frontend `PUT` to a temporary S3 key |
| Final physical object | Content-addressed `sha256/blob_hash` S3 key |
