import { FilesService, type PresignUploadRequest } from "@/client"

import { getFileCategory } from "./fileCategory"
import { calculateSha256 } from "./fileHash"

type UploadFileToCurrentFolderParams = {
  file: File
  currentPath: string
}

type DownloadFileParams = {
  id: string
  name: string
}

export async function uploadFileToCurrentFolder({
  file,
  currentPath,
}: UploadFileToCurrentFolderParams): Promise<void> {
  const mimeType = file.type || "application/octet-stream"
  const metadata: PresignUploadRequest = {
    folder_path: currentPath,
    name: file.name,
    mime_type: mimeType,
    category: getFileCategory(mimeType),
    blob_hash: await calculateSha256(file),
    size_bytes: file.size,
  }

  const presignResponse = await FilesService.presignUpload({
    requestBody: metadata,
  })

  const uploadResponse = await fetch(presignResponse.upload_url, {
    method: presignResponse.method || "PUT",
    headers: presignResponse.headers,
    body: file,
  })

  if (!uploadResponse.ok) {
    throw new Error("MinIO upload failed")
  }

  await FilesService.completeFileUpload({
    requestBody: metadata,
  })
}

export async function downloadFile({
  id,
  name,
}: DownloadFileParams): Promise<void> {
  const response = await FilesService.presignDownload({ fileId: id })
  const link = document.createElement("a")

  link.href = response.download_url
  link.download = name
  link.rel = "noopener"
  document.body.appendChild(link)
  link.click()
  link.remove()
}
