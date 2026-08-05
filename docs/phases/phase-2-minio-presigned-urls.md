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

## 2. Refactor backend project structure

Before adding presigned upload/download endpoints, split the file-storage backend code by responsibility.

The current structure is acceptable for a small starter app, but it is not the right shape for Phase 2 if MinIO, presigned URLs, metadata validation, and ownership checks are added directly to `backend/app/api/routes/files.py`.

Current problems:

- `backend/app/api/routes/files.py` mixes HTTP routing, folder lookup, lazy root creation, DB queries, and response construction.
- `backend/app/models.py` mixes global app models, DB tables, and API response schemas.
- Adding S3/MinIO calls directly to route handlers would make the API layer hard to test.
- `backend/app/crud.py` is template-style shared CRUD and should not become the file-storage dumping ground.

Recommended Phase 2 structure:

```text
backend/app/
  api/routes/files.py          # thin HTTP layer only
  files/
    __init__.py
    models.py                  # Folder, StoredFile, LtreeType
    schemas.py                 # file/folder request and response schemas
    repository.py              # SQL queries and persistence
    service.py                 # ownership checks, path lookup, upload/download orchestration
  core/storage.py              # configured S3/MinIO client and presigned URL helpers
```

Responsibilities:

- `api/routes/files.py`
  - parse request parameters and bodies;
  - inject `session` and `current_user`;
  - call file service functions;
  - return API schemas.
- `files/repository.py`
  - load folder by owner/path;
  - list folder children;
  - load files by id/owner;
  - insert file metadata;
  - enforce DB-facing duplicate checks where needed.
- `files/service.py`
  - validate ownership and folder existence;
  - keep lazy root-folder behavior explicit;
  - validate upload metadata;
  - coordinate repository and storage wrapper calls.
- `core/storage.py`
  - create the boto3 S3 client;
  - derive object keys;
  - generate presigned PUT/GET URLs;
  - call `head_object`;
  - rewrite Docker-internal MinIO URLs to browser-visible URLs when needed.

Refactor scope:

- Move only the file-storage domain first.
- Leave user/item/login/template code in the current layout unless it blocks Phase 2.
- Keep existing endpoint behavior stable during the refactor:
  ```text
  GET /api/v1/files?path=<ltree-path>
  ```
- Add tests around the refactored file service before adding upload/download endpoints.

### Phase 2.2 implementation plan

Goal: reorganize the file-storage backend code without changing API behavior.

This step should be a pure structure/refactor step. It should not add MinIO upload/download endpoints yet.

#### Step 1: Create the file-storage package

Add:

```text
backend/app/files/__init__.py
backend/app/files/models.py
backend/app/files/schemas.py
backend/app/files/repository.py
backend/app/files/service.py
```

No behavior change in this step.

#### Step 2: Move file-storage models and schemas

Move these classes out of `backend/app/models.py` into `backend/app/files/models.py`:

```text
LtreeType
FolderBase
Folder
StoredFileBase
StoredFile
```

Move these API schemas into `backend/app/files/schemas.py`:

```text
FolderPublic
StoredFilePublic
FolderContentPublic
FolderWithContentsPublic
```

`backend/app/models.py` should continue to hold unrelated template/domain models:

```text
User
Item
Token
Message
NewPassword
```

Compatibility option:

- If too many imports break at once, temporarily re-export file models/schemas from `backend/app/models.py`.
- Remove the compatibility exports after imports are updated.

Preferred final state:

```python
from app.files.models import Folder, StoredFile
from app.files.schemas import FolderWithContentsPublic
```

#### Step 3: Add repository functions

Add SQL-only functions to `backend/app/files/repository.py`.

Suggested functions:

```python
def get_folder_by_path(*, session, owner_id, path):
    ...


def create_root_folder(*, session, owner_id):
    ...


def list_child_folders(*, session, owner_id, parent_id):
    ...


def list_folder_files(*, session, owner_id, folder_id):
    ...


def get_file_by_id(*, session, owner_id, file_id):
    ...
```

Rules:

- repository functions should not know about FastAPI;
- repository functions should not raise `HTTPException`;
- repository functions should not generate API response schemas;
- repository functions should only query or persist data.

#### Step 4: Add file service functions

Add business logic to `backend/app/files/service.py`.

Suggested function:

```python
def get_folder_contents(*, session, owner_id, path):
    ...
```

Responsibilities:

- load folder by `owner_id + path`;
- if `path == "root"` and no root exists, create a real root folder row;
- return not-found state for missing non-root folders;
- call repository functions to load child folders and files;
- build `FolderWithContentsPublic`.

Keep lazy root creation explicit in this service. It currently creates a real DB row, not mock data.

#### Step 5: Make the API route thin

Update `backend/app/api/routes/files.py` so the route only:

1. receives `session`, `current_user`, and `path`;
2. calls `get_folder_contents`;
3. translates not-found errors into HTTP 404 if needed;
4. returns the schema.

Target route shape:

```python
@router.get("", response_model=FolderWithContentsPublic)
def read_files(
    session: SessionDep,
    current_user: CurrentUser,
    path: str = Query(default="root", min_length=1, max_length=1024),
) -> Any:
    return get_folder_contents(
        session=session,
        owner_id=current_user.id,
        path=path,
    )
```

If the service uses a domain exception, the route should translate it:

```python
except FolderNotFoundError:
    raise HTTPException(status_code=404, detail="Folder not found")
```

#### Step 6: Update imports

Replace imports from `app.models` for file-storage classes.

Examples:

```python
from app.files.models import Folder, StoredFile
from app.files.schemas import FolderContentPublic, FolderWithContentsPublic
```

Also check:

```text
backend/app/alembic/env.py
backend/app/initial_data.py
backend/app/api/routes/files.py
backend/tests
```

Alembic must still import all table models so metadata contains `folders` and `files`.

#### Step 7: Add tests for the refactored behavior

Add or update tests for current behavior:

- `GET /api/v1/files` returns root contents;
- `GET /api/v1/files?path=root.documents` returns that folder contents;
- missing non-root path returns 404;
- root path creates a real root folder row if missing;
- another user's folders/files are not returned.

Do not involve MinIO in these tests.

#### Step 8: Verify

Run:

```text
docker compose exec backend pytest
docker compose exec backend alembic current
docker compose exec backend python -c "from app.files.models import Folder, StoredFile; print(Folder.__tablename__, StoredFile.__tablename__)"
```

Manual API check:

```text
GET /api/v1/files
GET /api/v1/files?path=root.documents
```

Acceptance criteria:

- existing `GET /api/v1/files?path=<ltree-path>` behavior is unchanged;
- route file contains no raw SQLModel `select(...)` queries;
- file-storage DB models are no longer defined in global `app.models`;
- all file-storage API schemas live under `app.files.schemas`;
- tests pass without requiring MinIO.

## 3. Add API endpoints

Implement this as small Phase 2.3 slices. Each slice should be independently reviewable and should keep the app runnable.

### Phase 2.3.1: Storage wrapper foundation

Goal: add the MinIO/S3 integration layer without exposing new API behavior yet.

Files:

```text
backend/app/core/storage.py
backend/app/core/config.py
backend/pyproject.toml
backend/tests/core/test_storage.py
```

Work:

- add `boto3` dependency;
- confirm these settings exist in `backend/app/core/config.py`:
  ```text
  S3_ENDPOINT_URL
  S3_PUBLIC_ENDPOINT_URL
  S3_BUCKET
  S3_ACCESS_KEY
  S3_SECRET_KEY
  S3_REGION
  S3_PRESIGNED_URL_EXPIRES_SECONDS
  ```
- create a configured S3 client using those settings;
- add object-key helper:
  ```text
  sha256/{blob_hash}
  ```
- add presigned URL helpers for PUT and GET;
- add `head_object`/stat helper;
- add internal-to-public URL rewrite for local Docker:
  ```text
  http://minio:9000 -> http://localhost:9000
  ```

Implementation details:

```python
@dataclass(frozen=True)
class ObjectStat:
    size_bytes: int
    content_type: str | None = None


def get_object_key(blob_hash: str) -> str:
    ...


def get_s3_client() -> Any:
    ...


def create_presigned_upload_url(
    *,
    object_key: str,
    mime_type: str,
    expires_in: int | None = None,
) -> str:
    ...


def create_presigned_download_url(
    *,
    object_key: str,
    expires_in: int | None = None,
) -> str:
    ...


def stat_object(*, object_key: str) -> ObjectStat:
    ...
```

S3 client configuration:

```python
boto3.client(
    "s3",
    endpoint_url=settings.S3_ENDPOINT_URL,
    aws_access_key_id=settings.S3_ACCESS_KEY,
    aws_secret_access_key=settings.S3_SECRET_KEY,
    region_name=settings.S3_REGION,
)
```

Presigned PUT parameters:

```python
ClientMethod="put_object"
Params={
    "Bucket": settings.S3_BUCKET,
    "Key": object_key,
    "ContentType": mime_type,
}
ExpiresIn=expires_in or settings.S3_PRESIGNED_URL_EXPIRES_SECONDS
```

Presigned GET parameters:

```python
ClientMethod="get_object"
Params={
    "Bucket": settings.S3_BUCKET,
    "Key": object_key,
}
ExpiresIn=expires_in or settings.S3_PRESIGNED_URL_EXPIRES_SECONDS
```

URL rewrite rule:

- if `S3_ENDPOINT_URL != S3_PUBLIC_ENDPOINT_URL`, replace only the URL prefix;
- do not parse or rebuild the query string, because that can break the signature;
- example:
  ```text
  http://minio:9000/cloud-file-storage/sha256/abc?...
  -> http://localhost:9000/cloud-file-storage/sha256/abc?...
  ```

Error behavior:

- `stat_object` should return `ObjectStat` for an existing object;
- missing object should raise a storage-specific exception, for example:
  ```python
  class ObjectNotFoundError(Exception):
      pass
  ```
- do not raise `HTTPException` from `core/storage.py`;
- API-facing error translation belongs in later service/route slices.

Tests:

- unit-test `get_object_key`;
- unit-test internal-to-public URL rewrite;
- unit-test presigned PUT calls `generate_presigned_url` with `put_object`, bucket, key, content type, and expiry;
- unit-test presigned GET calls `generate_presigned_url` with `get_object`, bucket, key, and expiry;
- unit-test `stat_object` maps `ContentLength` and `ContentType` into `ObjectStat`;
- unit-test missing object maps to `ObjectNotFoundError`.

Mocking strategy:

- do not require real MinIO for tests in this slice;
- monkeypatch/mock `get_s3_client()` or the boto3 client object;
- verify parameters passed to the mocked client.

Acceptance criteria:

- `backend/app/core/storage.py` imports cleanly;
- object key generation is deterministic;
- storage wrapper can be unit-tested without FastAPI route changes;
- no new file API endpoints are exposed in this slice.
- Ruff passes for `backend/app/core/storage.py` and `backend/tests/core/test_storage.py`.
- Targeted storage tests pass.

Verification commands:

```text
docker compose exec backend ruff check app tests/core/test_storage.py
docker compose exec backend pytest tests/core/test_storage.py
docker compose exec backend python -c "from app.core.storage import get_object_key; print(get_object_key('abc'))"
```

### Phase 2.3.2: Upload/download API schemas and validation

Goal: define request/response contracts before implementing endpoint behavior.

This slice should add schemas and pure validation helpers only. It should not add the upload/download routes yet and should not call MinIO.

Files:

```text
backend/app/files/schemas.py
backend/app/files/service.py
backend/tests/files/test_schemas.py
```

Add schemas:

```text
PresignUploadRequest
PresignUploadResponse
CompleteUploadRequest
PresignDownloadResponse
```

Schema contracts:

```python
class FileCategory(str, Enum):
    image = "image"
    video = "video"
    audio = "audio"
    document = "document"
    spreadsheet = "spreadsheet"
    archive = "archive"
    other = "other"
```

```python
class PresignUploadRequest(SQLModel):
    folder_path: str
    name: str
    mime_type: str
    category: FileCategory
    blob_hash: str
    size_bytes: int
```

```python
class PresignUploadResponse(SQLModel):
    upload_url: str
    method: str = "PUT"
    headers: dict[str, str]
    object_key: str
    expires_in: int
```

```python
class CompleteUploadRequest(SQLModel):
    folder_path: str
    name: str
    mime_type: str
    category: FileCategory
    blob_hash: str
    size_bytes: int
```

```python
class PresignDownloadResponse(SQLModel):
    download_url: str
    method: str = "GET"
    expires_in: int
```

Validation rules:

- `folder_path` must be present;
- `folder_path` should use ltree-style path segments:
  ```text
  root
  root.documents
  root.projects.phase_2
  ```
- `blob_hash` must be 64 lowercase/uppercase hex characters;
- `size_bytes > 0`;
- `name` must be non-empty;
- `name` should not contain `/` because folder placement is controlled by `folder_path`;
- `mime_type` must be non-empty;
- `category` must be one of:
  ```text
  image
  video
  audio
  document
  spreadsheet
  archive
  other
  ```

Recommended implementation:

- keep request/response model definitions in `backend/app/files/schemas.py`;
- add shared validation helpers in the same file if they are schema-specific;
- if validation logic becomes larger, move pure helpers to:
  ```text
  backend/app/files/validation.py
  ```
- avoid route/service side effects in this slice.

Pydantic/SQLModel validation examples:

```python
SHA256_HEX_PATTERN = re.compile(r"^[a-fA-F0-9]{64}$")
LTREE_PATH_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\\.[A-Za-z_][A-Za-z0-9_]*)*$")
```

```python
@field_validator("blob_hash")
@classmethod
def validate_blob_hash(cls, value: str) -> str:
    if not SHA256_HEX_PATTERN.fullmatch(value):
        raise ValueError("blob_hash must be a 64-character SHA-256 hex string")
    return value.lower()
```

```python
@field_validator("folder_path")
@classmethod
def validate_folder_path(cls, value: str) -> str:
    if not LTREE_PATH_PATTERN.fullmatch(value):
        raise ValueError("folder_path must be a valid ltree path")
    return value
```

```python
@field_validator("name")
@classmethod
def validate_name(cls, value: str) -> str:
    if "/" in value:
        raise ValueError("name must not contain '/'")
    return value
```

Implementation notes:

- normalize `blob_hash` to lowercase after validation;
- keep `category` typed as an enum, not a free string;
- use `Field(min_length=1)` for `folder_path`, `name`, and `mime_type`;
- use `Field(gt=0)` for `size_bytes`;
- avoid adding object existence checks here; that belongs to Phase 2.3.4;
- avoid folder ownership checks here; that belongs to Phase 2.3.3/2.3.4 services.

Tests:

```text
backend/tests/files/test_schemas.py
```

Test cases:

- valid `PresignUploadRequest` accepts expected payload;
- valid `CompleteUploadRequest` accepts expected payload;
- uppercase `blob_hash` is accepted and normalized to lowercase;
- invalid short hash is rejected;
- invalid non-hex hash is rejected;
- `size_bytes = 0` is rejected;
- empty `folder_path` is rejected;
- invalid ltree path is rejected;
- filename containing `/` is rejected;
- invalid category is rejected;
- response schemas default method values to `PUT` and `GET`.

Acceptance criteria:

- invalid request payloads fail with 422;
- validation can be tested without MinIO;
- no DB insert happens in this slice.
- no new file API endpoints are exposed in this slice;
- schema tests pass without Docker/MinIO;
- Ruff passes for changed schema/test files.

Verification commands:

```text
uv run ruff check app/files/schemas.py tests/files/test_schemas.py
uv run pytest tests/files/test_schemas.py
```

### Phase 2.3.3: Presign upload endpoint

Goal: allow the frontend to request a short-lived presigned PUT URL.

Endpoint:

```text
POST /api/v1/files/presign-upload
```

Files:

```text
backend/app/api/routes/files.py
backend/app/files/service.py
backend/app/files/repository.py
backend/app/files/schemas.py
backend/app/core/storage.py
backend/tests/api/routes/test_files.py
```

Work:

- authenticate current user;
- validate request schema;
- load folder by `owner_id + folder_path`;
- return 404 if folder does not exist or does not belong to user;
- derive object key from `blob_hash`;
- generate presigned PUT URL;
- return URL, method, required headers, object key, and expiry.

Do not insert a `files` row here.

Service design:

Add a service function:

```python
def create_presigned_upload(
    *,
    session: Session,
    owner_id: uuid.UUID,
    request: PresignUploadRequest,
) -> PresignUploadResponse:
    ...
```

Responsibilities:

1. Load folder:
   ```python
   repository.get_folder_by_path(
       session=session,
       owner_id=owner_id,
       path=request.folder_path,
   )
   ```
2. If folder is missing, raise `FolderNotFoundError`.
3. Derive object key:
   ```python
   storage.get_object_key(request.blob_hash)
   ```
4. Generate presigned upload URL:
   ```python
   storage.create_presigned_upload_url(
       object_key=object_key,
       mime_type=request.mime_type,
   )
   ```
5. Return:
   ```python
   PresignUploadResponse(
       upload_url=upload_url,
       headers={"Content-Type": request.mime_type},
       object_key=object_key,
       expires_in=settings.S3_PRESIGNED_URL_EXPIRES_SECONDS,
   )
   ```

Route design:

Add to `backend/app/api/routes/files.py`:

```python
@router.post("/presign-upload", response_model=PresignUploadResponse)
def presign_upload(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    request: PresignUploadRequest,
) -> Any:
    try:
        return create_presigned_upload(
            session=session,
            owner_id=current_user.id,
            request=request,
        )
    except FolderNotFoundError:
        raise HTTPException(status_code=404, detail="Folder not found")
```

Important behavior:

- request validation happens through `PresignUploadRequest`;
- folder ownership is enforced by querying `owner_id + folder_path`;
- no `files` row is inserted;
- no `head_object` call is made;
- no file bytes pass through the backend.

Testing strategy:

- mock `app.files.service.storage.create_presigned_upload_url`;
- do not require real MinIO;
- create/use an owned folder in the test DB;
- call the API with auth headers;
- assert response shape and object key;
- assert no `StoredFile` row is created.

Test cases:

- success for owned folder;
- missing folder returns 404;
- invalid hash returns 422;
- unauthenticated request returns 401;
- another user's folder path returns 404 because lookup is scoped by owner;
- presign upload does not insert into `files`.

Acceptance criteria:

- owned folder returns a presigned upload response;
- missing folder returns 404;
- invalid hash returns 422;
- another user's folder cannot be used;
- storage wrapper is mocked in API tests.
- response includes:
  ```json
  {
    "method": "PUT",
    "headers": {
      "Content-Type": "<mime_type>"
    },
    "object_key": "sha256/<blob_hash>",
    "expires_in": 900
  }
  ```
- `files` table row count does not increase after presign upload.

Verification commands:

```text
uv run ruff check app/api/routes/files.py app/files/service.py tests/api/routes/test_files.py
uv run pytest tests/api/routes/test_files.py
```

### Phase 2.3.4: Complete upload endpoint

Goal: record file metadata only after the browser successfully uploads bytes to MinIO.

Endpoint:

```text
POST /api/v1/files/complete-upload
```

Work:

- authenticate current user;
- validate request schema;
- load folder by `owner_id + folder_path`;
- derive object key from `blob_hash`;
- call storage `head_object`;
- verify object exists;
- verify object size matches `size_bytes`;
- optionally verify content type matches `mime_type`;
- reject duplicate filename in the same folder;
- insert row into `files`;
- return created file metadata.

Acceptance criteria:

- successful completion inserts one `files` row;
- missing object is rejected;
- size mismatch is rejected;
- duplicate name in same folder is rejected;
- same `blob_hash` can still be used in another folder/name;
- `GET /api/v1/files?path=<folder_path>` shows the completed file.

### Phase 2.3.5: Presign download endpoint

Goal: allow the frontend to download a stored file through a short-lived presigned GET URL.

Endpoint:

```text
POST /api/v1/files/{file_id}/presign-download
```

Work:

- authenticate current user;
- load file by `owner_id + file_id`;
- return 404 if file does not exist or belongs to another user;
- derive object key from `file.blob_hash`;
- generate presigned GET URL;
- return URL, method, and expiry.

Acceptance criteria:

- owned file returns a presigned download URL;
- missing file returns 404;
- another user's file returns 404;
- storage wrapper is mocked in API tests.

### Phase 2.3.6: DB constraints and repository hardening

Goal: make file/folder uniqueness rules explicit at the database layer.

Work:

- add migration for:
  ```sql
  CREATE INDEX ix_files_owner_id ON files(owner_id);
  CREATE INDEX ix_files_folder_id ON files(folder_id);
  CREATE INDEX ix_files_blob_hash ON files(blob_hash);
  CREATE UNIQUE INDEX uq_files_folder_name ON files(folder_id, name);
  CREATE INDEX ix_folders_owner_id ON folders(owner_id);
  CREATE UNIQUE INDEX uq_folders_owner_path ON folders(owner_id, path);
  CREATE UNIQUE INDEX uq_folders_parent_name ON folders(parent_id, name);
  CREATE INDEX ix_folders_path_gist ON folders USING GIST(path);
  ```
- update repository/service code to translate duplicate filename conflicts into stable API errors.

Acceptance criteria:

- Alembic migration applies cleanly;
- duplicate file name in same folder is blocked;
- duplicate folder path per owner is blocked;
- existing folder listing still works.

### Phase 2.3.7: End-to-end local verification

Goal: verify the full local upload/download flow with MinIO.

Manual flow:

```text
1. Start compose stack.
2. Login in frontend or Swagger.
3. Request presigned upload URL.
4. PUT file bytes directly to MinIO.
5. Call complete-upload.
6. Refresh GET /api/v1/files?path=<current-path>.
7. Request presigned download URL.
8. Download file bytes from MinIO.
```

Acceptance criteria:

- MinIO bucket exists;
- upload URL works from browser/curl using `localhost:9000`;
- completed file appears in folder listing;
- download URL returns the uploaded bytes;
- backend never proxies file bytes.

### Endpoint detail: `POST /api/v1/files/presign-upload`

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

### Endpoint detail: `POST /api/v1/files/complete-upload`

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

### Endpoint detail: `POST /api/v1/files/{file_id}/presign-download`

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
backend file-storage structure refactor
storage wrapper
presign-upload endpoint
complete-upload endpoint
presign-download endpoint
DB indexes/constraints migration
backend tests with mocked storage
README update
```
