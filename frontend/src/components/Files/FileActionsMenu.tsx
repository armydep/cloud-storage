import { useMutation } from "@tanstack/react-query"
import { Download, EllipsisVertical, Loader2 } from "lucide-react"
import { useState } from "react"

import type { FolderContentPublic } from "@/client"
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
  file: FolderContentPublic
}

export default function FileActionsMenu({ file }: FileActionsMenuProps) {
  const [open, setOpen] = useState(false)
  const { showErrorToast } = useCustomToast()

  const downloadMutation = useMutation({
    mutationFn: () => downloadFile({ id: file.id, name: file.name }),
    onSuccess: () => setOpen(false),
    onError: () => {
      showErrorToast("Download link could not be created.")
    },
  })

  return (
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
          disabled={downloadMutation.isPending}
          onSelect={(event) => {
            event.preventDefault()
            downloadMutation.mutate()
          }}
        >
          <Download />
          Download
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
