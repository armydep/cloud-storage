import { useSuspenseQuery } from "@tanstack/react-query"
import { createFileRoute, useNavigate } from "@tanstack/react-router"
import { FolderOpen } from "lucide-react"
import { Suspense } from "react"
import { z } from "zod"

import { FilesService } from "@/client"
import { DataTable } from "@/components/Common/DataTable"
import { getColumns } from "@/components/Files/columns"
import PendingFiles from "@/components/Pending/PendingFiles"
import { Button } from "@/components/ui/button"

const filesSearchSchema = z.object({
  path: z.string().catch("root"),
})

function getFilesQueryOptions(path: string) {
  return {
    queryFn: () => FilesService.readFiles({ path }),
    queryKey: ["files", path],
  }
}

export const Route = createFileRoute("/_layout/files")({
  component: Files,
  validateSearch: filesSearchSchema,
  head: () => ({
    meta: [
      {
        title: "Files - Cloud File Storage",
      },
    ],
  }),
})

function PathBreadcrumbs({
  currentPath,
  onOpenFolder,
}: {
  currentPath: string
  onOpenFolder: (path: string) => void
}) {
  const parts = currentPath.split(".").filter(Boolean)
  const crumbs = parts.map((part, index) => ({
    label: part,
    path: parts.slice(0, index + 1).join("."),
  }))

  return (
    <div className="flex flex-wrap items-center gap-1 text-sm text-muted-foreground">
      <span>Current path:</span>
      {crumbs.map((crumb, index) => (
        <div key={crumb.path} className="flex items-center gap-1">
          {index > 0 && <span>/</span>}
          <Button
            variant="link"
            className="h-auto p-0 text-sm"
            onClick={() => onOpenFolder(crumb.path)}
          >
            {crumb.label}
          </Button>
        </div>
      ))}
    </div>
  )
}

function FilesTableContent({
  currentPath,
  onOpenFolder,
}: {
  currentPath: string
  onOpenFolder: (path: string) => void
}) {
  const { data: folder } = useSuspenseQuery(getFilesQueryOptions(currentPath))
  const columns = getColumns({ onOpenFolder })

  if (folder.contents.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center text-center py-12">
        <div className="rounded-full bg-muted p-4 mb-4">
          <FolderOpen className="h-8 w-8 text-muted-foreground" />
        </div>
        <h3 className="text-lg font-semibold">This folder is empty</h3>
        <p className="text-muted-foreground">
          Files and folders you add later will appear here.
        </p>
      </div>
    )
  }

  return <DataTable columns={columns} data={folder.contents} />
}

function FilesTable({
  currentPath,
  onOpenFolder,
}: {
  currentPath: string
  onOpenFolder: (path: string) => void
}) {
  return (
    <Suspense fallback={<PendingFiles />}>
      <FilesTableContent
        currentPath={currentPath}
        onOpenFolder={onOpenFolder}
      />
    </Suspense>
  )
}

function Files() {
  const { path } = Route.useSearch()
  const navigate = useNavigate()
  const currentPath = path || "root"

  const openFolder = (nextPath: string) => {
    navigate({
      to: "/files",
      search: { path: nextPath },
    })
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-2">
        <h1 className="text-2xl font-bold tracking-tight">Files</h1>
        <p className="text-muted-foreground">
          Browse the contents of your current directory
        </p>
        <PathBreadcrumbs currentPath={currentPath} onOpenFolder={openFolder} />
      </div>
      <FilesTable currentPath={currentPath} onOpenFolder={openFolder} />
    </div>
  )
}
