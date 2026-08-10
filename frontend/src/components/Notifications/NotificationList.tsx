import { Loader2 } from "lucide-react"

import type { NotificationPublic } from "@/client"
import { Button } from "@/components/ui/button"
import { renderNotificationText } from "@/features/notifications/renderNotification"
import {
  useMarkAllNotificationsRead,
  useMarkNotificationRead,
  useNotificationsList,
} from "@/hooks/useNotifications"
import { cn } from "@/lib/utils"

function NotificationRow({
  notification,
}: {
  notification: NotificationPublic
}) {
  const markRead = useMarkNotificationRead()
  const isUnread = notification.read_at == null

  return (
    <div
      className={cn(
        "flex items-start justify-between gap-3 rounded-md border p-3",
        isUnread ? "bg-accent/40" : "opacity-70",
      )}
    >
      <div className="min-w-0">
        <p className="text-sm">{renderNotificationText(notification)}</p>
        <p className="text-muted-foreground text-xs">
          {new Date(notification.created_at).toLocaleString()}
        </p>
      </div>
      {isUnread && (
        <Button
          type="button"
          variant="ghost"
          size="sm"
          disabled={markRead.isPending}
          onClick={() => markRead.mutate(notification.id)}
        >
          Mark read
        </Button>
      )}
    </div>
  )
}

export function NotificationList({ open }: { open: boolean }) {
  const query = useNotificationsList(open)
  const markAllRead = useMarkAllNotificationsRead()
  const notifications = query.data?.pages.flatMap((page) => page.data) ?? []
  const hasUnread = notifications.some((item) => item.read_at == null)

  if (query.isPending) {
    return (
      <div
        role="status"
        className="text-muted-foreground flex items-center gap-2 px-4 pb-4 text-sm"
      >
        <Loader2 className="size-4 animate-spin" />
        Loading notifications…
      </div>
    )
  }

  if (query.isError) {
    return (
      <div className="text-destructive px-4 pb-4 text-sm">
        Notifications could not be loaded.
      </div>
    )
  }

  return (
    <div className="flex flex-1 flex-col gap-3 overflow-hidden px-4 pb-4">
      <div className="flex justify-end">
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={!hasUnread || markAllRead.isPending}
          onClick={() => markAllRead.mutate()}
        >
          Mark all read
        </Button>
      </div>
      <div className="flex flex-col gap-2 overflow-y-auto">
        {notifications.length === 0 ? (
          <p className="text-muted-foreground text-sm">No notifications yet.</p>
        ) : (
          notifications.map((notification) => (
            <NotificationRow
              key={notification.id}
              notification={notification}
            />
          ))
        )}
      </div>
      {query.hasNextPage && (
        <Button
          type="button"
          variant="ghost"
          size="sm"
          disabled={query.isFetchingNextPage}
          onClick={() => query.fetchNextPage()}
        >
          {query.isFetchingNextPage ? "Loading…" : "Load more"}
        </Button>
      )}
    </div>
  )
}
