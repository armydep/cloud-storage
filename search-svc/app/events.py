# These names are a contract with the backend, not a shared import -- see
# docs/phases/phase-10-search-service.md decision 1 and constraint 3.
# backend/app/notifications/events.py defines the same strings.
FILE_CREATED = "file_created"
FILE_DELETED = "file_deleted"
FOLDER_DELETED = "folder_deleted"
