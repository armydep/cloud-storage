import type { ColumnDef } from "@tanstack/react-table"
import { Check, Copy, File, Folder } from "lucide-react"

import type { FolderContentPublic } from "@/client"
import { Button } from "@/components/ui/button"
import { useCopyToClipboard } from "@/hooks/useCopyToClipboard"

function CopyId({ id }: { id: string }) {
  const [copiedText, copy] = useCopyToClipboard()
  const isCopied = copiedText === id

  return (
    <div className="flex items-center gap-1.5 group">
      <span className="font-mono text-xs text-muted-foreground">{id}</span>
      <Button
        variant="ghost"
        size="icon"
        className="size-6 opacity-0 group-hover:opacity-100 transition-opacity"
        onClick={() => copy(id)}
      >
        {isCopied ? (
          <Check className="size-3 text-green-500" />
        ) : (
          <Copy className="size-3" />
        )}
        <span className="sr-only">Copy ID</span>
      </Button>
    </div>
  )
}

function formatSize(value?: number | null) {
  if (value == null) {
    return "—"
  }
  return new Intl.NumberFormat(undefined, {
    maximumFractionDigits: 1,
    notation: "compact",
  }).format(value)
}

export const columns: ColumnDef<FolderContentPublic>[] = [
  {
    accessorKey: "name",
    header: "Name",
    cell: ({ row }) => {
      const isFolder = row.original.type === "folder"
      const Icon = isFolder ? Folder : File
      return (
        <div className="flex items-center gap-2">
          <Icon className={isFolder ? "size-4 text-blue-500" : "size-4 text-muted-foreground"} />
          <span className="font-medium">{row.original.name}</span>
        </div>
      )
    },
  },
  {
    accessorKey: "file_type",
    header: "Type",
    cell: ({ row }) => (
      <span className="text-muted-foreground">
        {row.original.type === "folder"
          ? "folder"
          : row.original.mime_type || row.original.category || "file"}
      </span>
    ),
  },
  {
    accessorKey: "path",
    header: "Path / Hash",
    cell: ({ row }) => (
      <span className="max-w-xs truncate block font-mono text-xs text-muted-foreground">
        {row.original.path || row.original.blob_hash || "—"}
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
    accessorKey: "id",
    header: "ID",
    cell: ({ row }) => <CopyId id={row.original.id} />,
  },
]
