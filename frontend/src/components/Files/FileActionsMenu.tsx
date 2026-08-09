import { useMutation } from "@tanstack/react-query"
import { Download, EllipsisVertical, Loader2, Share2 } from "lucide-react"
import { useState } from "react"

import type { FolderContentPublic } from "@/client"
import DeleteFileDialog from "@/components/Files/DeleteFileDialog"
import ShareFileDialog from "@/components/Files/ShareFileDialog"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { downloadFile } from "@/features/files"
import useCustomToast from "@/hooks/useCustomToast"

type FileActionsMenuProps = {
  currentPath: string
  file: FolderContentPublic
}

export default function FileActionsMenu({
  currentPath,
  file,
}: FileActionsMenuProps) {
  const [open, setOpen] = useState(false)
  const [shareOpen, setShareOpen] = useState(false)
  const [deleteOpen, setDeleteOpen] = useState(false)
  const { showErrorToast } = useCustomToast()

  const downloadMutation = useMutation({
    mutationFn: () => downloadFile({ id: file.id, name: file.name }),
    onSuccess: () => setOpen(false),
    onError: () => {
      showErrorToast("Download link could not be created.")
    },
  })

  return (
    <>
      <DropdownMenu open={open} onOpenChange={setOpen}>
        <DropdownMenuTrigger asChild>
          <Button
            variant="ghost"
            size="icon"
            disabled={downloadMutation.isPending}
          >
            {downloadMutation.isPending ? (
              <Loader2 className="animate-spin" />
            ) : (
              <EllipsisVertical />
            )}
            <span className="sr-only">Open file actions</span>
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuItem
            onSelect={() => {
              setOpen(false)
              setShareOpen(true)
            }}
          >
            <Share2 />
            Share
          </DropdownMenuItem>
          <DropdownMenuItem
            disabled={downloadMutation.isPending}
            onSelect={(event) => {
              event.preventDefault()
              downloadMutation.mutate()
            }}
          >
            <Download />
            Download
          </DropdownMenuItem>
          <DeleteFileDialog
            currentPath={currentPath}
            fileId={file.id}
            fileName={file.name}
            open={deleteOpen}
            onOpenChange={setDeleteOpen}
            onMenuClose={() => setOpen(false)}
          />
        </DropdownMenuContent>
      </DropdownMenu>
      <ShareFileDialog
        fileId={file.id}
        fileName={file.name}
        open={shareOpen}
        onOpenChange={setShareOpen}
      />
    </>
  )
}
