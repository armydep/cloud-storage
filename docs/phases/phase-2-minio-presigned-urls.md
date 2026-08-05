# Phase 2: MinIO and Presigned File Uploads

## Goal

Add MinIO as the local S3-compatible object store and implement backend APIs for direct browser upload/download using presigned URLs.

The backend remains responsible for:

- authentication and authorization;
- folder ownership checks;
- file metadata stored in Postgres;
- generating short-lived presigned URLs.

MinIO stores the actual file bytes.

```text
Frontend
  |
  | request presigned upload/download URL
  v
Backend API
  |
  | metadata and ownership checks
  v
Postgres: folders, files
  |
  | object operations
  v
MinIO: file bytes
```

## Current data model fit

The current file schema already fits this direction:

```text
folders
- id
- owner_id
- parent_id
- path ltree
- name

files
- id
- owner_id
- folder_id
- name
- mime_type
- category
- blob_hash
- size_bytes
```

`blob_hash` is the SHA-256 hash of the uploaded file content. The MinIO object key should be derived from it:

```text
sha256/{blob_hash}
```

This preserves the meaning of `blob_hash` and allows object-level deduplication.

## 1. Add MinIO to the setup

Add MinIO to local Docker Compose.

Recommended `compose.override.yml` services:

```yaml
minio:
  image: minio/minio
  command: server /data --console-address ":9001"
  ports:
    - "9000:9000" # S3 API
    - "9001:9001" # MinIO console
  environment:
    MINIO_ROOT_USER: ${MINIO_ROOT_USER:-minioadmin}
    MINIO_ROOT_PASSWORD: ${MINIO_ROOT_PASSWORD:-minioadmin}
  volumes:
    - minio-data:/data

minio-create-bucket:
  image: minio/mc
  depends_on:
    - minio
  entrypoint: >
    /bin/sh -c "
    mc alias set local http://minio:9000 ${MINIO_ROOT_USER:-minioadmin} ${MINIO_ROOT_PASSWORD:-minioadmin};
    mc mb -p local/${S3_BUCKET:-cloud-file-storage};
    exit 0;
    "
```

Add volume:

```yaml
volumes:
  minio-data:
```

Local URLs:

```text
MinIO S3 API:  http://localhost:9000
MinIO console: http://localhost:9001
```

## Backend environment

Add backend settings:

```env
S3_ENDPOINT_URL=http://minio:9000
S3_PUBLIC_ENDPOINT_URL=http://localhost:9000
S3_BUCKET=cloud-file-storage
S3_ACCESS_KEY=minioadmin
S3_SECRET_KEY=minioadmin
S3_REGION=us-east-1
S3_PRESIGNED_URL_EXPIRES_SECONDS=900
```

Why two endpoints:

- `S3_ENDPOINT_URL` is used by the backend container to talk to MinIO on the Docker network.
- `S3_PUBLIC_ENDPOINT_URL` is used in URLs returned to the browser.

In local Docker, the backend can reach:

```text
http://minio:9000
```

But the browser cannot. The browser needs:

```text
http://localhost:9000
```

This means generated presigned URLs may need host replacement before returning them to the frontend.

## Backend dependency

Add:

```text
boto3
```

Optional later:

```text
python-magic
filetype
```

Those can be used for server-side MIME validation, but Phase 2 can initially accept MIME/category from the frontend and validate the shape.

## 2. Add API endpoints

### `POST /api/v1/files/presign-upload`

Creates a short-lived presigned PUT URL for direct upload to MinIO.

Request:

```json
{
  "folder_path": "root.documents",
  "name": "report.pdf",
  "mime_type": "application/pdf",
  "category": "document",
  "blob_hash": "5f70bf18...",
  "size_bytes": 248320
}
```

Response:

```json
{
  "upload_url": "http://localhost:9000/cloud-file-storage/sha256/5f70bf18...?X-Amz-Signature=...",
  "method": "PUT",
  "headers": {
    "Content-Type": "application/pdf"
  },
  "object_key": "sha256/5f70bf18...",
  "expires_in": 900
}
```

Backend behavior:

1. Authenticate current user.
2. Validate `folder_path` exists and belongs to current user.
3. Validate `blob_hash`, `name`, `mime_type`, `category`, and `size_bytes`.
4. Derive object key:
   ```text
   sha256/{blob_hash}
   ```
5. Generate presigned PUT URL.
6. Return URL and required headers.

### `POST /api/v1/files/complete-upload`

Records uploaded file metadata after the browser successfully uploads to MinIO.

Request:

```json
{
  "folder_path": "root.documents",
  "name": "report.pdf",
  "mime_type": "application/pdf",
  "category": "document",
  "blob_hash": "5f70bf18...",
  "size_bytes": 248320
}
```

Response:

```json
{
  "id": "cd3e6e5c-0c5d-4ec8-8c7f-81d81070f3ed",
  "owner_id": "0ce5d6d4-6d65-4032-8571-c560b03b5310",
  "folder_id": "9f23b079-4d95-46cb-b57d-7430118b1d6e",
  "name": "report.pdf",
  "mime_type": "application/pdf",
  "category": "document",
  "blob_hash": "5f70bf18...",
  "size_bytes": 248320
}
```

Backend behavior:

1. Authenticate current user.
2. Validate folder ownership.
3. Derive object key:
   ```text
   sha256/{blob_hash}
   ```
4. Call `head_object` on MinIO to verify the object exists.
5. Verify object size matches `size_bytes`.
6. Optionally verify object content type matches `mime_type`.
7. Insert the row into `files`.
8. Return created file metadata.

Do not insert the DB row before upload completion. Otherwise the DB can point to missing objects.

### `POST /api/v1/files/{file_id}/presign-download`

Creates a short-lived presigned GET URL for direct browser download from MinIO.

Response:

```json
{
  "download_url": "http://localhost:9000/cloud-file-storage/sha256/5f70bf18...?X-Amz-Signature=...",
  "method": "GET",
  "expires_in": 900
}
```

Backend behavior:

1. Authenticate current user.
2. Load file by `file_id`.
3. Verify `file.owner_id == current_user.id`.
4. Derive object key:
   ```text
   sha256/{file.blob_hash}
   ```
5. Generate presigned GET URL.
6. Return URL.

## Upload flow

```text
1. Frontend computes SHA-256 of selected file.
2. Frontend calls POST /api/v1/files/presign-upload.
3. Backend validates folder ownership and returns a presigned PUT URL.
4. Frontend uploads file directly to MinIO with PUT.
5. Frontend calls POST /api/v1/files/complete-upload.
6. Backend verifies object exists in MinIO.
7. Backend inserts metadata into Postgres.
8. Frontend refreshes GET /api/v1/files?path=<current-path>.
```

## Download flow

```text
1. Frontend calls POST /api/v1/files/{file_id}/presign-download.
2. Backend verifies ownership.
3. Backend returns presigned GET URL.
4. Browser downloads directly from MinIO.
```

## Storage wrapper

Add:

```text
backend/app/core/storage.py
```

Responsibilities:

- create configured boto3 S3 client;
- derive object keys;
- generate presigned PUT URLs;
- generate presigned GET URLs;
- perform `head_object`;
- rewrite internal MinIO URLs to public browser URLs when needed.

Suggested API:

```python
def get_object_key(blob_hash: str) -> str:
    return f"sha256/{blob_hash}"


def create_presigned_upload_url(
    *, object_key: str, mime_type: str
) -> str:
    ...


def create_presigned_download_url(*, object_key: str) -> str:
    ...


def stat_object(*, object_key: str) -> ObjectStat:
    ...
```

## Validation rules

For upload presign and complete upload:

- `folder_path` must exist and belong to current user.
- `blob_hash` must be valid SHA-256 hex:
  ```text
  64 hex characters
  ```
- `size_bytes > 0`.
- `name` is not empty.
- `mime_type` is not empty.
- `category` is one of:
  ```text
  image
  video
  audio
  document
  spreadsheet
  archive
  other
  ```

For complete upload:

- MinIO object exists.
- MinIO object size matches `size_bytes`.
- Optional: MinIO object content type matches `mime_type`.

## Conflict behavior

Recommended Phase 2 behavior:

- reject duplicate file names in the same folder:
  ```text
  UNIQUE(folder_id, name)
  ```
- allow same `blob_hash` in different folders or with different names.

This gives deduplication at object level while preserving normal folder semantics.

## Recommended DB indexes and constraints

For files:

```sql
CREATE INDEX ix_files_owner_id ON files(owner_id);
CREATE INDEX ix_files_folder_id ON files(folder_id);
CREATE INDEX ix_files_blob_hash ON files(blob_hash);
CREATE UNIQUE INDEX uq_files_folder_name ON files(folder_id, name);
```

For folders:

```sql
CREATE INDEX ix_folders_owner_id ON folders(owner_id);
CREATE UNIQUE INDEX uq_folders_owner_path ON folders(owner_id, path);
CREATE UNIQUE INDEX uq_folders_parent_name ON folders(parent_id, name);
CREATE INDEX ix_folders_path_gist ON folders USING GIST(path);
```

## Backend tests

Do not require real MinIO for backend unit/API tests.

Mock the storage wrapper:

- presigned upload URL generation;
- presigned download URL generation;
- object stat/head operation.

Test cases:

- presign upload succeeds for owned folder;
- presign upload fails for missing folder;
- presign upload rejects invalid SHA-256;
- complete upload succeeds after mocked `head_object`;
- complete upload rejects size mismatch;
- complete upload rejects duplicate filename in same folder;
- presign download succeeds for owned file;
- presign download rejects another user's file;
- presign download rejects missing file.

Important: the current backend test fixture has previously deleted local dev users. Phase 2 should isolate tests from the local dev database before adding broader test coverage.

## Frontend assumptions for Phase 2

Frontend should:

- compute SHA-256 before presign upload;
- send file metadata to backend;
- upload directly to `upload_url`;
- call complete-upload after successful PUT;
- refresh the current folder listing;
- request presigned download URL before downloading.

## Deliverables

```text
compose MinIO service
bucket bootstrap service
backend S3 config
boto3 dependency
storage wrapper
presign-upload endpoint
complete-upload endpoint
presign-download endpoint
DB indexes/constraints migration
backend tests with mocked storage
README update
```
