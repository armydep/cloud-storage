import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Trash2 } from "lucide-react"
import { useForm } from "react-hook-form"

import { FilesService } from "@/client"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { DropdownMenuItem } from "@/components/ui/dropdown-menu"
import { LoadingButton } from "@/components/ui/loading-button"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

type DeleteFileDialogProps = {
  currentPath: string
  fileId: string
  fileName: string
  open: boolean
  onOpenChange: (open: boolean) => void
  onMenuClose: () => void
}

export default function DeleteFileDialog({
  currentPath,
  fileId,
  fileName,
  open,
  onOpenChange,
  onMenuClose,
}: DeleteFileDialogProps) {
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const { handleSubmit } = useForm()

  const mutation = useMutation({
    mutationFn: () => FilesService.deleteOwnedFile({ fileId }),
    onSuccess: () => {
      showSuccessToast("File deleted successfully")
      onOpenChange(false)
      onMenuClose()
      queryClient.invalidateQueries({ queryKey: ["files", currentPath] })
      queryClient.invalidateQueries({ queryKey: ["shared-files"] })
    },
    onError: handleError.bind(showErrorToast),
  })

  const onSubmit = () => {
    mutation.mutate()
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DropdownMenuItem
        variant="destructive"
        onSelect={(event) => event.preventDefault()}
        onClick={() => onOpenChange(true)}
      >
        <Trash2 />
        Delete
      </DropdownMenuItem>
      <DialogContent className="sm:max-w-md">
        <form onSubmit={handleSubmit(onSubmit)}>
          <DialogHeader>
            <DialogTitle>Delete file</DialogTitle>
            <DialogDescription>
              <span>
                <strong>{fileName}</strong> will be permanently deleted. This
                action cannot be undone.
              </span>
            </DialogDescription>
          </DialogHeader>

          <DialogFooter className="mt-4">
            <DialogClose asChild>
              <Button variant="outline" disabled={mutation.isPending}>
                Cancel
              </Button>
            </DialogClose>
            <LoadingButton
              variant="destructive"
              type="submit"
              loading={mutation.isPending}
            >
              Delete
            </LoadingButton>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
