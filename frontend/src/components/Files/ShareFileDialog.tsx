import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Loader2, Trash2 } from "lucide-react"
import { useForm } from "react-hook-form"
import { z } from "zod"

import {
  ApiError,
  type FileSharePublic,
  type FileSharesPublic,
  FilesService,
} from "@/client"
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

const fileSharesQueryKey = (fileId: string) => ["file-shares", fileId]

function ShareRecipient({
  fileId,
  share,
}: {
  fileId: string
  share: FileSharePublic
}) {
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const mutation = useMutation({
    mutationFn: () =>
      FilesService.deleteFileShare({ fileId, shareId: share.id }),
    onSuccess: () => {
      queryClient.setQueryData<FileSharesPublic>(
        fileSharesQueryKey(fileId),
        (current) => {
          if (!current) return current
          const data = current.data.filter((item) => item.id !== share.id)
          return { data, count: data.length }
        },
      )
      void queryClient.invalidateQueries({
        queryKey: fileSharesQueryKey(fileId),
      })
      showSuccessToast("Access revoked")
    },
    onError: () => showErrorToast("Access could not be revoked. Try again."),
  })

  return (
    <div className="flex items-center justify-between gap-3 rounded-md border p-3">
      <span className="min-w-0 truncate text-sm">{share.recipient_email}</span>
      <Button
        type="button"
        variant="ghost"
        size="icon"
        disabled={mutation.isPending}
        onClick={() => mutation.mutate()}
      >
        {mutation.isPending ? <Loader2 className="animate-spin" /> : <Trash2 />}
        <span className="sr-only">
          Revoke access for {share.recipient_email}
        </span>
      </Button>
    </div>
  )
}

export default function ShareFileDialog({
  fileId,
  fileName,
  open,
  onOpenChange,
}: ShareFileDialogProps) {
  const queryClient = useQueryClient()
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
      void queryClient.invalidateQueries({
        queryKey: fileSharesQueryKey(fileId),
      })
      form.reset()
      onOpenChange(false)
    },
    onError: (error: Error) => showErrorToast(shareErrorMessage(error)),
  })

  const sharesQuery = useQuery({
    queryKey: fileSharesQueryKey(fileId),
    queryFn: () => FilesService.readFileShares({ fileId }),
    enabled: open,
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
              <div className="grid gap-2">
                <h3 className="text-sm font-medium">People with access</h3>
                {sharesQuery.isPending ? (
                  <div
                    role="status"
                    className="flex items-center gap-2 text-sm text-muted-foreground"
                  >
                    <Loader2 className="size-4 animate-spin" />
                    Loading recipients…
                  </div>
                ) : sharesQuery.isError ? (
                  <div className="flex items-center justify-between gap-3 rounded-md border border-destructive/50 p-3">
                    <span className="text-sm text-destructive">
                      Recipients could not be loaded.
                    </span>
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      disabled={sharesQuery.isFetching}
                      onClick={() => sharesQuery.refetch()}
                    >
                      {sharesQuery.isFetching ? "Retrying…" : "Retry"}
                    </Button>
                  </div>
                ) : sharesQuery.data.data.length === 0 ? (
                  <p className="text-sm text-muted-foreground">
                    This file is not shared with anyone yet.
                  </p>
                ) : (
                  <div className="grid max-h-48 gap-2 overflow-y-auto">
                    {sharesQuery.data.data.map((share) => (
                      <ShareRecipient
                        key={share.id}
                        fileId={fileId}
                        share={share}
                      />
                    ))}
                  </div>
                )}
              </div>
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
