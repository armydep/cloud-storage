import { useMutation, useSuspenseQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import type { ColumnDef } from "@tanstack/react-table"
import { Download, File, Loader2, Share2 } from "lucide-react"
import { Suspense } from "react"

import { FilesService, type SharedFilePublic } from "@/client"
import { DataTable } from "@/components/Common/DataTable"
import { Button } from "@/components/ui/button"
import { downloadFile } from "@/features/files"
import useCustomToast from "@/hooks/useCustomToast"

const sharedFilesQueryOptions = {
  queryFn: () => FilesService.readFilesSharedWithMe(),
  queryKey: ["shared-files"],
}

export const Route = createFileRoute("/_layout/shared-with-me")({
  component: SharedWithMe,
  head: () => ({
    meta: [{ title: "Shared with me - Cloud File Storage" }],
  }),
})

function formatSize(value: number): string {
  return new Intl.NumberFormat(undefined, {
    maximumFractionDigits: 1,
    notation: "compact",
  }).format(value)
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(
    new Date(value),
  )
}

function DownloadSharedFile({ file }: { file: SharedFilePublic }) {
  const { showErrorToast } = useCustomToast()
  const mutation = useMutation({
    mutationFn: () => downloadFile({ id: file.id, name: file.name }),
    onError: () => showErrorToast("Download link could not be created."),
  })

  return (
    <Button
      variant="ghost"
      size="icon"
      disabled={mutation.isPending}
      onClick={() => mutation.mutate()}
    >
      {mutation.isPending ? <Loader2 className="animate-spin" /> : <Download />}
      <span className="sr-only">Download {file.name}</span>
    </Button>
  )
}

const columns: ColumnDef<SharedFilePublic>[] = [
  {
    accessorKey: "name",
    header: "Name",
    cell: ({ row }) => (
      <div className="flex items-center gap-2">
        <File className="size-4 text-muted-foreground" />
        <span className="font-medium">{row.original.name}</span>
      </div>
    ),
  },
  { accessorKey: "owner_email", header: "Owner" },
  {
    accessorKey: "mime_type",
    header: "Type",
    cell: ({ row }) => (
      <span className="text-muted-foreground">
        {row.original.mime_type || row.original.category}
      </span>
    ),
  },
  {
    accessorKey: "size_bytes",
    header: "Size",
    cell: ({ row }) => (
      <span className="text-muted-foreground">
        {formatSize(row.original.size_bytes)}
      </span>
    ),
  },
  {
    accessorKey: "shared_at",
    header: "Shared",
    cell: ({ row }) => (
      <span className="text-muted-foreground">
        {formatDate(row.original.shared_at)}
      </span>
    ),
  },
  {
    id: "actions",
    header: () => <span className="sr-only">Actions</span>,
    cell: ({ row }) => (
      <div className="flex justify-end">
        <DownloadSharedFile file={row.original} />
      </div>
    ),
  },
]

function SharedFilesContent() {
  const { data: sharedFiles } = useSuspenseQuery(sharedFilesQueryOptions)

  if (sharedFiles.data.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-center">
        <div className="mb-4 rounded-full bg-muted p-4">
          <Share2 className="h-8 w-8 text-muted-foreground" />
        </div>
        <h3 className="text-lg font-semibold">No files shared with you</h3>
        <p className="text-muted-foreground">
          Files other users share with you will appear here.
        </p>
      </div>
    )
  }

  return <DataTable columns={columns} data={sharedFiles.data} />
}

function SharedWithMe() {
  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-2">
        <h1 className="text-2xl font-bold tracking-tight">Shared with me</h1>
        <p className="text-muted-foreground">
          Download files that other users have shared with you.
        </p>
      </div>
      <Suspense
        fallback={
          <div
            role="status"
            className="py-12 text-center text-muted-foreground"
          >
            Loading shared files…
          </div>
        }
      >
        <SharedFilesContent />
      </Suspense>
    </div>
  )
}
