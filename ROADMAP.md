# Product Roadmap

This document tracks the planned direction of Cloud File Storage. It describes
outcomes and phases at a high level; implementation details and day-to-day work
belong in GitHub Issues.

The roadmap is expected to change as the project evolves. Items within a phase
are not necessarily listed in implementation order.

## 1. Current focus: File and folder management

Complete the core operations needed to manage a cloud-style file hierarchy.

- [ ] **1.1** Create folders ([#37](https://github.com/armydep/cloude-file-storage/issues/37))
- [ ] **1.2** Rename folders ([#38](https://github.com/armydep/cloude-file-storage/issues/38))
- [ ] **1.3** Rename files ([#39](https://github.com/armydep/cloude-file-storage/issues/39))
- [x] **1.4** Delete files ([#40](https://github.com/armydep/cloude-file-storage/issues/40),
      [design](docs/phases/phase-6-delete-file.md))
- [x] **1.5** Delete folders ([#41](https://github.com/armydep/cloude-file-storage/issues/41),
      [design](docs/phases/phase-7-delete-folder.md))
- [ ] **1.6** Define and enforce file and folder name validation, including
      allowed characters and maximum name length

## 2. Engineering foundations

Keep development and delivery reliable while product capabilities expand.

- [x] **2.1** Run backend integration tests in isolated Testcontainers environments
      ([#43](https://github.com/armydep/cloude-file-storage/issues/43))
- [ ] **2.2** Fix and stabilize CI workflows
      ([#42](https://github.com/armydep/cloude-file-storage/issues/42))
- [ ] **2.3** Add automated coverage for new file and folder operations
- [ ] **2.4** Define validation, conflict, and error-handling conventions
- [ ] **2.5** Enable TLS for all production-facing endpoints
- [ ] **2.6** Verify upload hashes with S3-side checksums
      ([#91](https://github.com/armydep/cloude-file-storage/issues/91))
- [ ] **2.7** Delay file blob row locks until upload metadata mutation
      ([#92](https://github.com/armydep/cloude-file-storage/issues/92))

## 3. Next phase: File experience

Improve the main file-management workflow after the core operations are stable.

- [ ] **3.1** Drag-and-drop uploads
- [ ] **3.2** Upload progress, cancellation, and retry
- [ ] **3.3** Multi-file upload
- [ ] **3.4** Sorting, filtering, and search
- [ ] **3.5** File previews and metadata details
- [ ] **3.6** Bulk selection and bulk actions
- [ ] **3.7** Add creation timestamps to files
- [ ] **3.8** Enforce a maximum file size
- [ ] **3.9** Support resumable uploads
- [ ] **3.10** Support resumable downloads

## 4. Next phase: User experience and notifications

- [ ] **4.1** Send a welcome email after registration
- [ ] **4.2** Set per-user storage quotas
- [ ] **4.3** Notify users when they reach or approach their quota

## 5. Later phase: Mobile and synchronization

- [ ] **5.1** Build an Android client
      ([#47](https://github.com/armydep/cloude-file-storage/issues/47))
- [ ] **5.2** Synchronize files between the Android client and cloud storage

## 6. Later phase: Sharing and collaboration

- [x] **6.1** Share files with specific users
      ([#48](https://github.com/armydep/cloude-file-storage/issues/48),
      [design](docs/phases/phase-4-file-sharing.md))
- [ ] **6.2** Share folders with specific users
- [ ] **6.3** Share files and folders publicly with anyone
- [ ] **6.4** Create expiring public links
- [ ] **6.5** Add read-only and edit permissions
- [ ] **6.6** Record file and folder activity
- [ ] **6.7** Add notifications for shared content

## 7. Later phase: Storage and reliability

- [ ] **7.1** File version history and restoration
- [ ] **7.2** Trash with a retention period and recovery
- [ ] **7.3** Storage usage reporting
- [ ] **7.4** Add an asynchronous cleanup process for S3 objects that have no metadata reference
- [ ] **7.5** Add an asynchronous cleanup process for metadata records whose S3 objects are missing
- [ ] **7.6** Integrity checks for database metadata and stored objects
- [ ] **7.7** Backup and disaster-recovery procedures

## 8. Later phase: Architecture and scale

- [ ] **8.1** Split the application into independently deployable services
- [ ] **8.2** Split backend file transfers into dedicated upload and download services
- [ ] **8.3** Add an API gateway in front of the services

## 9. Completed foundations

- [x] **9.1** Authenticated private workspaces
- [x] **9.2** Folder navigation and content listing
- [x] **9.3** PostgreSQL metadata storage
- [x] **9.4** MinIO-backed object storage
- [x] **9.5** Presigned file upload and download flows
- [x] **9.6** Frontend upload and download integration

Detailed design documents:

- **9.7** [Phase 2: MinIO and presigned file uploads](docs/phases/phase-2-minio-presigned-urls.md)
- **9.8** [Phase 3: Frontend upload and download](docs/phases/phase-3-frontend-upload-download.md)

## 10. Adding roadmap items

When proposing a future capability:

- **10.1** Add the outcome to the appropriate phase in this document.
- **10.2** Open a GitHub Issue when the work is ready to be specified and scheduled.
- **10.3** Link the issue from the roadmap entry.
- **10.4** Move delivered capabilities to **Completed foundations** or a release note.
