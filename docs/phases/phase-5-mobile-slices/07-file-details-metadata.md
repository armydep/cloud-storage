# Slice 7: File details and metadata

## Outcome
A signed-in user can tap a file to view its metadata in a detail screen showing size, creation date, MIME type, and owner.

## Roadmap
ROADMAP 5.1

## Acceptance criteria
- [ ] Tapping a file in the folder list opens a detail screen (not available for folders)
- [ ] Detail screen displays file name as title
- [ ] Detail screen displays file size in human-readable format (B, KB, MB, GB)
- [ ] Detail screen displays file creation date in local timezone, human-readable format
- [ ] Detail screen displays MIME type (e.g., "application/pdf")
- [ ] Detail screen displays owner email address
- [ ] Detail screen has a "Close" or back button to return to folder list
- [ ] Backend returns `created_at` and `owner_email` in folder contents response
- [ ] Mobile app parses and displays these fields
- [ ] Tests cover detail screen rendering with complete metadata

## Out of scope
- Editing file metadata
- Deleting files from detail screen (separate slice)
- Sharing files from detail screen (separate phase - ROADMAP 6)
- Download history or access timestamps

## Open questions
1. Should the backend enhance `FolderContentPublic` schema to include `created_at` and `owner_email`, or create a separate GET `/api/v1/files/{id}` detail endpoint?
2. Should the detail screen include file category icon/badge?
3. Should date display include timestamp (e.g., "Feb 8, 2026 at 2:34 PM") or just date?

## Implementation notes
- File detail screen should be a separate Widget, navigated to from FileListItem
- Use DateTime parsing and local timezone formatting
- Reuse `displaySize` helper from FileContent model for consistent formatting
- Detail screen should be scrollable for very long owner emails or file names
