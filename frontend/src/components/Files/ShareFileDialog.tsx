import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation } from "@tanstack/react-query"
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
  recipientEmail: z
    .string()
    .trim()
    .min(1, { message: "Recipient email is required" })
    .email({ message: "Enter a valid email address" }),
})

type FormData = z.infer<typeof formSchema>

type ShareFileDialogProps = {
  fileId: string
  fileName: string
  open: boolean
  onOpenChange: (open: boolean) => void
}

function apiDetail(error: ApiError): string | undefined {
  if (
    typeof error.body === "object" &&
    error.body !== null &&
    "detail" in error.body &&
    typeof error.body.detail === "string"
  ) {
    return error.body.detail
  }
  return undefined
}

function shareErrorMessage(error: Error): string {
  if (!(error instanceof ApiError)) {
    return "File sharing failed. Try again."
  }

  const detail = apiDetail(error)
  if (error.status === 409) {
    return "This file is already shared with that user."
  }
  if (detail === "Recipient not found") {
    return "No account exists for that email address."
  }
  if (detail === "Recipient is inactive") {
    return "That user account is inactive."
  }
  if (detail === "A file cannot be shared with its owner") {
    return "You cannot share a file with yourself."
  }
  if (error.status === 404) {
    return "The file is no longer available."
  }
  return "File sharing failed. Try again."
}

export default function ShareFileDialog({
  fileId,
  fileName,
  open,
  onOpenChange,
}: ShareFileDialogProps) {
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const form = useForm<FormData>({
    resolver: zodResolver(formSchema),
    defaultValues: { recipientEmail: "" },
  })

  const mutation = useMutation({
    mutationFn: ({ recipientEmail }: FormData) =>
      FilesService.createFileShare({
        fileId,
        requestBody: { recipient_email: recipientEmail },
      }),
    onSuccess: () => {
      showSuccessToast("File shared successfully")
      form.reset()
      onOpenChange(false)
    },
    onError: (error: Error) => showErrorToast(shareErrorMessage(error)),
  })

  const handleOpenChange = (nextOpen: boolean) => {
    if (!nextOpen && mutation.isPending) {
      return
    }
    if (!nextOpen) {
      form.reset()
    }
    onOpenChange(nextOpen)
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Share file</DialogTitle>
          <DialogDescription>
            Give another user download access to {fileName}.
          </DialogDescription>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit((data) => mutation.mutate(data))}>
            <div className="grid gap-4 py-4">
              <FormField
                control={form.control}
                name="recipientEmail"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Recipient email</FormLabel>
                    <FormControl>
                      <Input
                        autoFocus
                        autoComplete="email"
                        inputMode="email"
                        placeholder="user@example.com"
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
                <Button
                  type="button"
                  variant="outline"
                  disabled={mutation.isPending}
                >
                  Cancel
                </Button>
              </DialogClose>
              <LoadingButton type="submit" loading={mutation.isPending}>
                Share
              </LoadingButton>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  )
}
