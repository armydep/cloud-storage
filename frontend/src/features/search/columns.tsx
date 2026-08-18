import type { ColumnDef } from "@tanstack/react-table"

import type { FolderContentPublic } from "@/client"
import {
  FileNameContent,
  formatDate,
  formatSize,
} from "@/components/Files/columns"
import FileActionsMenu from "@/components/Files/FileActionsMenu"
import type { SearchResultItem } from "@/search-client"

function asFileRow(result: SearchResultItem): FolderContentPublic {
  return {
    id: result.id,
    name: result.name,
    type: "file",
    mime_type: result.mime_type,
    category: result.category,
    size_bytes: result.size_bytes,
    created_at: result.created_at,
  }
}

export function getSearchColumns(): ColumnDef<SearchResultItem>[] {
  return [
    {
      accessorKey: "name",
      header: "Name",
      cell: ({ row }) => (
        <div className="flex items-center gap-2">
          <FileNameContent name={row.original.name} />
        </div>
      ),
    },
    {
      accessorKey: "folder_path",
      header: "Folder",
      cell: ({ row }) => (
        <span className="text-muted-foreground">
          {row.original.folder_path}
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
      id: "actions",
      header: () => <span className="sr-only">Actions</span>,
      cell: ({ row }) => (
        <div className="flex justify-end">
          <FileActionsMenu
            currentPath={row.original.folder_path}
            file={asFileRow(row.original)}
          />
        </div>
      ),
    },
  ]
}
