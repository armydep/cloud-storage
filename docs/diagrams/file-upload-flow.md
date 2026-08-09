# File Upload Flow

This diagram shows the Phase 2 upload flow using presigned URLs. The backend authorizes the operation and stores metadata; the browser uploads file bytes directly to MinIO. Upload completion verifies object metadata before taking the `file_blobs` row lock; the lock is held only while mutating blob claims, ref counts, and file metadata.

```mermaid
sequenceDiagram
    participant User
    participant Frontend
    participant Backend as "Backend API"
    participant DB as "Postgres"
    participant MinIO

    User->>Frontend: Select file to upload
    Frontend->>Frontend: Compute SHA-256 blob_hash
    Frontend->>Backend: POST presign upload
    Backend->>DB: Find folder by owner_id + folder_path
    alt Folder missing or not owned
        DB-->>Backend: No folder
        Backend-->>Frontend: 404 Folder not found
    else Folder exists
        DB-->>Backend: Folder
        Backend->>Backend: Derive pending upload key
        Backend->>MinIO: Generate checksum-signed presigned PUT URL
        MinIO-->>Backend: Presigned upload URL
        Backend-->>Frontend: upload_url, method=PUT, checksum headers, object_key, expires_in
    end

    Frontend->>MinIO: PUT file bytes with x-amz-checksum-sha256
    MinIO-->>Frontend: Upload success

    Frontend->>Backend: POST complete upload

    Backend->>DB: Find folder by owner_id + folder_path
    alt Folder missing or not owned
        DB-->>Backend: No folder
        Backend-->>Frontend: 404 Folder not found
    else Folder exists
        DB-->>Backend: Folder
        Backend->>DB: Check duplicate filename in folder
        alt Duplicate filename
            DB-->>Backend: Existing file
            Backend-->>Frontend: 409 File name already exists
        else No duplicate
            Backend->>DB: Read file_blobs by hash without row lock
            Backend->>DB: Find existing blob claim
            alt Blob already claimed by this user
                Backend->>DB: SELECT file_blobs FOR UPDATE
                Backend->>DB: Increment ref_count and insert files row
                DB-->>Backend: Stored file metadata
                Backend-->>Frontend: StoredFilePublic
            else Pending proof required
                Backend->>DB: Find pending upload
                Backend->>MinIO: HEAD pending upload with ChecksumMode=ENABLED
                alt Pending object missing
                    MinIO-->>Backend: Not found
                    Backend-->>Frontend: 400 Uploaded object not found
                else Object exists
                    MinIO-->>Backend: size_bytes, content_type, checksum_sha256
                    alt Size/content/checksum validation fails
                        Backend-->>Frontend: 400 Uploaded object validation error
                    else Object metadata valid
                        opt Canonical blob row missing
                            Backend->>MinIO: Copy pending object to canonical sha256 key
                        end
                        Backend->>DB: SELECT file_blobs FOR UPDATE
                        Backend->>DB: Ensure blob claim, increment ref_count, insert files row
                        DB-->>Backend: Stored file metadata
                        Backend->>MinIO: Delete pending upload object
                        Backend-->>Frontend: StoredFilePublic
                    end
                end
            end
            Frontend->>Backend: GET current folder listing
            Backend->>DB: List folder contents
            DB-->>Backend: Folders + files
            Backend-->>Frontend: Updated folder listing
        end
    end
```

## Happy Path

```mermaid
sequenceDiagram
    participant User
    participant Frontend
    participant Backend as "Backend API"
    participant DB as "Postgres"
    participant MinIO

    User->>Frontend: Select file
    Frontend->>Frontend: Compute blob hash
    Frontend->>Backend: Request upload URL
    Backend->>DB: Verify target folder
    DB-->>Backend: Folder found
    Backend->>Backend: Build pending upload key and checksum header
    Backend->>MinIO: Create checksum-signed presigned PUT URL
    MinIO-->>Backend: Upload URL
    Backend-->>Frontend: Upload URL and headers
    Frontend->>MinIO: Upload file bytes with checksum header
    MinIO-->>Frontend: Upload success
    Frontend->>Backend: Complete upload
    Backend->>DB: Read blob metadata without row lock
    alt Blob already claimed by this user
        Backend->>DB: Skip pending upload verification
    else Pending proof required
        Backend->>MinIO: Verify pending object metadata and checksum
        MinIO-->>Backend: Object metadata and checksum
        opt Blob does not already exist
            Backend->>MinIO: Copy pending object to canonical key
        end
    end
    Backend->>DB: Lock blob row and save claim/ref_count/file metadata
    DB-->>Backend: Stored file
    opt Pending proof was used
        Backend->>MinIO: Delete pending object
    end
    Backend-->>Frontend: File metadata
    Frontend->>Backend: Refresh folder listing
    Backend->>DB: Load folder contents
    DB-->>Backend: Current contents
    Backend-->>Frontend: Updated file list
```
