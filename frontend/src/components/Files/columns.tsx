import type { ColumnDef } from "@tanstack/react-table"
import { Check, Copy, File, Folder } from "lucide-react"

import type { FolderContentPublic } from "@/client"
import FileActionsMenu from "@/components/Files/FileActionsMenu"
import FolderActionsMenu from "@/components/Files/FolderActionsMenu"
import { Button } from "@/components/ui/button"
import { useCopyToClipboard } from "@/hooks/useCopyToClipboard"

type FilesColumnsOptions = {
  currentPath: string
  onOpenFolder: (path: string) => void
}

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

function formatDate(value?: string | null) {
  if (!value) {
    return "—"
  }

  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return "—"
  }

  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date)
}

export function getColumns({
  currentPath,
  onOpenFolder,
}: FilesColumnsOptions): ColumnDef<FolderContentPublic>[] {
  return [
    {
      accessorKey: "name",
      header: "Name",
      cell: ({ row }) => {
        const isFolder = row.original.type === "folder"
        const Icon = isFolder ? Folder : File
        const nameContent = (
          <>
            <Icon
              className={
                isFolder
                  ? "size-4 text-blue-500"
                  : "size-4 text-muted-foreground"
              }
            />
            <span className="font-medium">{row.original.name}</span>
          </>
        )

        if (isFolder && row.original.path) {
          return (
            <button
              className="flex items-center gap-2 rounded-sm text-left hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              type="button"
              onClick={() => onOpenFolder(row.original.path as string)}
            >
              {nameContent}
            </button>
          )
        }

        return <div className="flex items-center gap-2">{nameContent}</div>
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
      accessorKey: "created_at",
      header: "Created",
      cell: ({ row }) => (
        <span className="text-muted-foreground">
          {formatDate(row.original.created_at)}
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
    {
      id: "actions",
      header: () => <span className="sr-only">Actions</span>,
      cell: ({ row }) => {
        return (
          <div className="flex justify-end">
            {row.original.type === "folder" ? (
              <FolderActionsMenu
                currentPath={currentPath}
                folder={row.original}
              />
            ) : (
              <FileActionsMenu currentPath={currentPath} file={row.original} />
            )}
          </div>
        )
      },
    },
  ]
}
