# File Upload Flow

This diagram shows the Phase 2 upload flow using presigned URLs. The backend authorizes the operation and stores metadata; the browser uploads file bytes directly to MinIO.

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
        Backend->>Backend: Derive object key from blob hash
        Backend->>MinIO: Generate presigned PUT URL
        MinIO-->>Backend: Presigned upload URL
        Backend-->>Frontend: upload_url, method=PUT, headers, object_key, expires_in
    end

    Frontend->>MinIO: PUT file bytes to upload_url
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
            Backend->>Backend: Derive object key from blob hash
            Backend->>MinIO: HEAD object_key
            alt Object missing
                MinIO-->>Backend: Not found
                Backend-->>Frontend: 400 Uploaded object not found
            else Object exists
                MinIO-->>Backend: size_bytes, content_type
                alt Size/content validation fails
                    Backend-->>Frontend: 400 Uploaded object validation error
                else Object metadata valid
                    Backend->>DB: Insert files row
                    DB-->>Backend: Stored file metadata
                    Backend-->>Frontend: StoredFilePublic
                    Frontend->>Backend: GET current folder listing
                    Backend->>DB: List folder contents
                    DB-->>Backend: Folders + files
                    Backend-->>Frontend: Updated folder listing
                end
            end
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
    Backend->>Backend: Build object key
    Backend->>MinIO: Create presigned PUT URL
    MinIO-->>Backend: Upload URL
    Backend-->>Frontend: Upload URL and headers
    Frontend->>MinIO: Upload file bytes
    MinIO-->>Frontend: Upload success
    Frontend->>Backend: Complete upload
    Backend->>MinIO: Verify uploaded object
    MinIO-->>Backend: Object metadata
    Backend->>DB: Save file metadata
    DB-->>Backend: Stored file
    Backend-->>Frontend: File metadata
    Frontend->>Backend: Refresh folder listing
    Backend->>DB: Load folder contents
    DB-->>Backend: Current contents
    Backend-->>Frontend: Updated file list
```
