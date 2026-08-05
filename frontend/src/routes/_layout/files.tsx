import { useSuspenseQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { FolderOpen } from "lucide-react"
import { Suspense } from "react"

import { DataTable } from "@/components/Common/DataTable"
import { columns } from "@/components/Files/columns"
import PendingFiles from "@/components/Pending/PendingFiles"
import { FilesService } from "@/client"

function getRootFilesQueryOptions() {
  return {
    queryFn: () => FilesService.readRootFileEntry(),
    queryKey: ["files", "root"],
  }
}

export const Route = createFileRoute("/_layout/files")({
  component: Files,
  head: () => ({
    meta: [
      {
        title: "Files - Cloud File Storage",
      },
    ],
  }),
})

function FilesTableContent() {
  const { data: root } = useSuspenseQuery(getRootFilesQueryOptions())

  if (root.contents.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center text-center py-12">
        <div className="rounded-full bg-muted p-4 mb-4">
          <FolderOpen className="h-8 w-8 text-muted-foreground" />
        </div>
        <h3 className="text-lg font-semibold">Your root folder is empty</h3>
        <p className="text-muted-foreground">
          Files and folders you add later will appear here.
        </p>
      </div>
    )
  }

  return <DataTable columns={columns} data={root.contents} />
}

function FilesTable() {
  return (
    <Suspense fallback={<PendingFiles />}>
      <FilesTableContent />
    </Suspense>
  )
}

function Files() {
  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Files</h1>
        <p className="text-muted-foreground">
          Browse the contents of your root directory
        </p>
      </div>
      <FilesTable />
    </div>
  )
}
