import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Upload } from "lucide-react"
import { useRef } from "react"

import { ApiError } from "@/client"
import { Button } from "@/components/ui/button"
import useCustomToast from "@/hooks/useCustomToast"
import { uploadFileToCurrentFolder } from "@/features/files"

type UploadFileButtonProps = {
  currentPath: string
}

function getUploadErrorMessage(error: Error) {
  if (error instanceof ApiError && error.status === 409) {
    return "A file with this name already exists in this folder."
  }

  return "Upload failed. Try again."
}

export default function UploadFileButton({
  currentPath,
}: UploadFileButtonProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()

  const uploadMutation = useMutation({
    mutationFn: (file: File) => uploadFileToCurrentFolder({ file, currentPath }),
    onSuccess: () => {
      showSuccessToast("File uploaded successfully")
      queryClient.invalidateQueries({ queryKey: ["files", currentPath] })
    },
    onError: (error: Error) => {
      showErrorToast(getUploadErrorMessage(error))
    },
    onSettled: () => {
      if (inputRef.current) {
        inputRef.current.value = ""
      }
    },
  })

  const openFilePicker = () => {
    inputRef.current?.click()
  }

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]

    if (!file) {
      return
    }

    uploadMutation.mutate(file)
  }

  return (
    <>
      <input
        ref={inputRef}
        className="hidden"
        type="file"
        onChange={handleFileChange}
        disabled={uploadMutation.isPending}
      />
      <Button
        className="my-4"
        type="button"
        onClick={openFilePicker}
        disabled={uploadMutation.isPending}
      >
        <Upload className="mr-2" />
        {uploadMutation.isPending ? "Uploading..." : "Upload"}
      </Button>
    </>
  )
}
