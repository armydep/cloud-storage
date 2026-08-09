import { EllipsisVertical } from "lucide-react"
import { useState } from "react"

import type { FolderContentPublic } from "@/client"
import DeleteFolderDialog from "@/components/Files/DeleteFolderDialog"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"

type FolderActionsMenuProps = {
  currentPath: string
  folder: FolderContentPublic
}

export default function FolderActionsMenu({
  currentPath,
  folder,
}: FolderActionsMenuProps) {
  const [open, setOpen] = useState(false)
  const [deleteOpen, setDeleteOpen] = useState(false)

  return (
    <DropdownMenu open={open} onOpenChange={setOpen}>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon">
          <EllipsisVertical />
          <span className="sr-only">Open folder actions</span>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DeleteFolderDialog
          currentPath={currentPath}
          folderId={folder.id}
          folderName={folder.name}
          open={deleteOpen}
          onOpenChange={setDeleteOpen}
          onMenuClose={() => setOpen(false)}
        />
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
