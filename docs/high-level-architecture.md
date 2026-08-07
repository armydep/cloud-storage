# High-Level Architecture

This document describes the current high-level architecture of Cloud File Storage.
It focuses on runtime components and the main request and file-transfer paths.

## System architecture

```mermaid
flowchart LR
    User[Web user]
    Mobile[Flutter Android app<br/>Authentication implemented;<br/>file management planned]

    subgraph Edge[Edge / Web tier]
        Traefik[Traefik<br/>TLS termination and routing]
        Frontend[React web application]
    end

    subgraph Application[Application tier]
        API[FastAPI backend<br/>JWT authentication<br/>File/folder metadata API<br/>Sharing and presigned URLs]

        Routes[API routes]
        Service[File service layer]
        Repository[Repository layer]
        StorageAdapter[S3 storage adapter]

        API --> Routes
        Routes --> Service
        Service --> Repository
        Service --> StorageAdapter
    end

    subgraph Data[Data tier]
        Postgres[(PostgreSQL<br/>users, folders, files,<br/>file shares)]
        ObjectStorage[(S3-compatible object storage<br/>MinIO locally<br/>File bytes keyed by SHA-256)]
    end

    Email[SMTP email service<br/>Mailcatcher locally]

    User -->|HTTPS| Traefik
    Traefik -->|Serve SPA| Frontend
    Frontend -->|REST API + Bearer JWT| Traefik
    Traefik -->|/ API traffic| API

    Mobile -->|REST API + Bearer JWT| Traefik

    Repository -->|SQLModel / SQLAlchemy| Postgres
    StorageAdapter -->|HEAD / object verification| ObjectStorage
    API -->|Password recovery email| Email

    Service -.->|Return short-lived<br/>presigned PUT / GET URL| Frontend
    Frontend ==>|Upload / download file bytes directly| ObjectStorage
```

## Main architectural idea

The backend is the **control plane** for authentication, authorization, folder and
file metadata, sharing rules, and generation of short-lived presigned URLs.
PostgreSQL stores application metadata, while the actual file bytes live in
S3-compatible object storage.

File bytes do **not** normally pass through the FastAPI service. The web client
uploads and downloads directly to/from object storage using presigned URLs. This
keeps API instances out of the high-bandwidth file-transfer path.

## Backend layering

The file-management backend is separated by responsibility:

```mermaid
flowchart LR
    HTTP[FastAPI route handlers<br/>app/api/routes/files.py]
    Domain[File service<br/>app/files/service.py]
    Repo[Repository<br/>app/files/repository.py]
    Storage[Storage adapter<br/>app/core/storage.py]
    DB[(PostgreSQL)]
    S3[(S3 / MinIO)]

    HTTP --> Domain
    Domain --> Repo
    Repo --> DB
    Domain --> Storage
    Storage --> S3
```

- **Routes** translate HTTP requests/responses and domain errors.
- **Service layer** implements file/folder ownership, sharing, upload-completion,
  and presign workflows.
- **Repository layer** owns database queries and persistence.
- **Storage adapter** isolates S3-compatible operations and presigned URL creation.

## Upload flow

```mermaid
sequenceDiagram
    participant W as React web app
    participant A as FastAPI backend
    participant P as PostgreSQL
    participant S as S3 / MinIO

    W->>W: Calculate SHA-256 and file metadata
    W->>A: POST /files/presign-upload
    A->>P: Validate user and destination folder
    A-->>W: Presigned PUT URL
    W->>S: PUT file bytes directly
    W->>A: POST /files/complete-upload
    A->>S: HEAD object / verify size and type
    A->>P: Insert file metadata
    A-->>W: Stored file metadata
```

Object keys are content-addressed using the current pattern:

```text
sha256/<blob_hash>
```

## Download flow

```mermaid
sequenceDiagram
    participant W as Web or authorized client
    participant A as FastAPI backend
    participant P as PostgreSQL
    participant S as S3 / MinIO

    W->>A: POST /files/{file_id}/presign-download
    A->>P: Verify ownership or file share access
    A-->>W: Presigned GET URL
    W->>S: GET file bytes directly
```

## Authentication

The FastAPI backend authenticates users with email/password and issues JWT access
tokens. Authenticated API requests use:

```text
Authorization: Bearer <access-token>
```

The React application uses the backend API for authenticated operations. The
Flutter Android client currently supports sign-in, secure token persistence,
session restoration, and sign-out; Android file management and synchronization
are planned rather than part of the current implementation.

## Deployment and local development

Production-style Compose configuration contains the core services:

- Traefik
- React frontend
- FastAPI backend
- PostgreSQL
- a prestart/migration task

The local Compose override additionally provides development infrastructure such
as MinIO, Mailcatcher, Adminer, and Playwright. MinIO is the local
S3-compatible implementation used by the direct file-transfer flow.
