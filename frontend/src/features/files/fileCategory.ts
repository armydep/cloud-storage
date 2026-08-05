import type { FileCategory } from "@/client"

const SPREADSHEET_MIME_TYPES = new Set([
  "application/vnd.ms-excel",
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  "application/vnd.oasis.opendocument.spreadsheet",
  "text/csv",
])

const ARCHIVE_MIME_TYPES = new Set([
  "application/zip",
  "application/x-zip-compressed",
  "application/x-tar",
  "application/gzip",
  "application/x-gzip",
  "application/vnd.rar",
  "application/x-rar-compressed",
  "application/x-7z-compressed",
])

const DOCUMENT_MIME_TYPES = new Set([
  "application/pdf",
  "application/msword",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  "application/vnd.oasis.opendocument.text",
  "application/rtf",
])

export function getFileCategory(mimeType: string): FileCategory {
  const normalizedMimeType = mimeType.trim().toLowerCase()

  if (!normalizedMimeType) {
    return "other"
  }

  if (normalizedMimeType.startsWith("image/")) {
    return "image"
  }

  if (normalizedMimeType.startsWith("video/")) {
    return "video"
  }

  if (normalizedMimeType.startsWith("audio/")) {
    return "audio"
  }

  if (SPREADSHEET_MIME_TYPES.has(normalizedMimeType)) {
    return "spreadsheet"
  }

  if (ARCHIVE_MIME_TYPES.has(normalizedMimeType)) {
    return "archive"
  }

  if (
    normalizedMimeType.startsWith("text/") ||
    DOCUMENT_MIME_TYPES.has(normalizedMimeType)
  ) {
    return "document"
  }

  return "other"
}
