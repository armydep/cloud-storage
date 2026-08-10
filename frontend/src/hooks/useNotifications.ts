import {
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query"

import { NotificationsService } from "@/client"
import { useDocumentVisibility } from "./useDocumentVisibility"

// Within the 15-30s window from phase-9-in-app-notifications.md decision 5.
const POLL_INTERVAL_MS = 20_000

const unreadCountKey = ["notifications", "unread-count"] as const
const listKey = ["notifications", "list"] as const

export function useUnreadCount() {
  const visible = useDocumentVisibility()

  return useQuery({
    queryKey: unreadCountKey,
    queryFn: () => NotificationsService.readUnreadCount(),
    // `false` (not just a long interval) so a tab left open overnight stops
    // polling entirely rather than backing off — decision 5 / constraint 5.
    refetchInterval: visible ? POLL_INTERVAL_MS : false,
  })
}

export function useNotificationsList(enabled: boolean) {
  const visible = useDocumentVisibility()

  return useInfiniteQuery({
    queryKey: listKey,
    queryFn: ({ pageParam }) =>
      NotificationsService.readNotifications({ cursor: pageParam, limit: 20 }),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (lastPage) => lastPage.next_cursor ?? undefined,
    enabled,
    refetchInterval: enabled && visible ? POLL_INTERVAL_MS : false,
  })
}

export function useMarkNotificationRead() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (notificationId: string) =>
      NotificationsService.readNotification({ notificationId }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: listKey })
      void queryClient.invalidateQueries({ queryKey: unreadCountKey })
    },
  })
}

export function useMarkAllNotificationsRead() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: () => NotificationsService.readAllNotifications(),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: listKey })
      void queryClient.invalidateQueries({ queryKey: unreadCountKey })
    },
  })
}
