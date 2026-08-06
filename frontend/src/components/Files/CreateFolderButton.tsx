import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { FolderPlus } from "lucide-react"
import { useState } from "react"
import { useForm } from "react-hook-form"
import { z } from "zod"

import { ApiError, FilesService } from "@/client"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form"
import { Input } from "@/components/ui/input"
import { LoadingButton } from "@/components/ui/loading-button"
import useCustomToast from "@/hooks/useCustomToast"

const formSchema = z.object({
  name: z
    .string()
    .trim()
    .min(1, { message: "Folder name is required" })
    .max(255, { message: "Folder name must be 255 characters or fewer" }),
})

type FormData = z.infer<typeof formSchema>

function folderErrorMessage(error: Error) {
  if (error instanceof ApiError && error.status === 409) {
    return "A folder with this name already exists in this folder."
  }
  if (error instanceof ApiError && error.status === 404) {
    return "The current folder no longer exists."
  }
  return "Folder creation failed. Try again."
}

export default function CreateFolderButton({
  currentPath,
}: {
  currentPath: string
}) {
  const [isOpen, setIsOpen] = useState(false)
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const form = useForm<FormData>({
    resolver: zodResolver(formSchema),
    defaultValues: { name: "" },
  })

  const mutation = useMutation({
    mutationFn: ({ name }: FormData) =>
      FilesService.createChildFolder({
        requestBody: { parent_path: currentPath, name },
      }),
    onSuccess: () => {
      showSuccessToast("Folder created successfully")
      queryClient.invalidateQueries({ queryKey: ["files", currentPath] })
      form.reset()
      setIsOpen(false)
    },
    onError: (error: Error) => showErrorToast(folderErrorMessage(error)),
  })

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <DialogTrigger asChild>
        <Button className="my-4" variant="outline">
          <FolderPlus className="mr-2" />
          New folder
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Create folder</DialogTitle>
          <DialogDescription>
            Create a folder inside the current directory.
          </DialogDescription>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit((data) => mutation.mutate(data))}>
            <div className="grid gap-4 py-4">
              <FormField
                control={form.control}
                name="name"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Folder name</FormLabel>
                    <FormControl>
                      <Input
                        autoFocus
                        maxLength={255}
                        placeholder="Project files"
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>
            <DialogFooter>
              <DialogClose asChild>
                <Button variant="outline" disabled={mutation.isPending}>
                  Cancel
                </Button>
              </DialogClose>
              <LoadingButton type="submit" loading={mutation.isPending}>
                Create
              </LoadingButton>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  )
}
