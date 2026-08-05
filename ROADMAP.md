# Product Roadmap

This document tracks the planned direction of Cloud File Storage. It describes
outcomes and phases at a high level; implementation details and day-to-day work
belong in GitHub Issues.

The roadmap is expected to change as the project evolves. Items within a phase
are not necessarily listed in implementation order.

## Current focus: File and folder management

Complete the core operations needed to manage a cloud-style file hierarchy.

- [ ] Create folders ([#37](https://github.com/armydep/cloude-file-storage/issues/37))
- [ ] Rename folders ([#38](https://github.com/armydep/cloude-file-storage/issues/38))
- [ ] Rename files ([#39](https://github.com/armydep/cloude-file-storage/issues/39))
- [ ] Delete files ([#40](https://github.com/armydep/cloude-file-storage/issues/40))
- [ ] Delete folders ([#41](https://github.com/armydep/cloude-file-storage/issues/41))

## Engineering foundations

Keep development and delivery reliable while product capabilities expand.

- [ ] Run backend integration tests in isolated Testcontainers environments
      ([#43](https://github.com/armydep/cloude-file-storage/issues/43))
- [ ] Fix and stabilize CI workflows
      ([#42](https://github.com/armydep/cloude-file-storage/issues/42))
- [ ] Add automated coverage for new file and folder operations
- [ ] Define validation, conflict, and error-handling conventions

## Next phase: File experience

Improve the main file-management workflow after the core operations are stable.

- [ ] Drag-and-drop uploads
- [ ] Upload progress, cancellation, and retry
- [ ] Multi-file upload
- [ ] Sorting, filtering, and search
- [ ] File previews and metadata details
- [ ] Bulk selection and bulk actions
- [ ] Add creation timestamps to files
- [ ] Enforce a maximum file size
- [ ] Support resumable uploads
- [ ] Support resumable downloads

## Next phase: User experience and notifications

- [ ] Send a welcome email after registration
- [ ] Set per-user storage quotas
- [ ] Notify users when they reach or approach their quota

## Later phase: Mobile and synchronization

- [ ] Build an Android client
- [ ] Synchronize files between the Android client and cloud storage

## Later phase: Sharing and collaboration

- [ ] Share files with specific users
- [ ] Share folders with specific users
- [ ] Share files and folders publicly with anyone
- [ ] Create expiring public links
- [ ] Add read-only and edit permissions
- [ ] Record file and folder activity
- [ ] Add notifications for shared content

## Later phase: Storage and reliability

- [ ] File version history and restoration
- [ ] Trash with a retention period and recovery
- [ ] Storage usage reporting
- [ ] Add an asynchronous cleanup process for S3 objects that have no metadata reference
- [ ] Add an asynchronous cleanup process for metadata records whose S3 objects are missing
- [ ] Integrity checks for database metadata and stored objects
- [ ] Backup and disaster-recovery procedures

## Later phase: Architecture and scale

- [ ] Split the application into independently deployable services
- [ ] Add an API gateway in front of the services

## Completed foundations

- [x] Authenticated private workspaces
- [x] Folder navigation and content listing
- [x] PostgreSQL metadata storage
- [x] MinIO-backed object storage
- [x] Presigned file upload and download flows
- [x] Frontend upload and download integration

Detailed design documents:

- [Phase 2: MinIO and presigned file uploads](docs/phases/phase-2-minio-presigned-urls.md)
- [Phase 3: Frontend upload and download](docs/phases/phase-3-frontend-upload-download.md)

## Adding roadmap items

When proposing a future capability:

1. Add the outcome to the appropriate phase in this document.
2. Open a GitHub Issue when the work is ready to be specified and scheduled.
3. Link the issue from the roadmap entry.
4. Move delivered capabilities to **Completed foundations** or a release note.
