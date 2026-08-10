import type { NotificationPublic } from "@/client"

/**
 * Notification rows carry `event_type` + a structured `payload`, never
 * rendered text (see phase-9-in-app-notifications.md decision 6). This is
 * the one place that turns that structured data into copy, so wording
 * changes never require a migration.
 */
export function renderNotificationText(
  notification: NotificationPublic,
): string {
  const { event_type, payload } = notification

  if (event_type === "file_shared") {
    const sharerEmail = payload.sharer_email
    const fileName = payload.file_name
    if (typeof sharerEmail === "string" && typeof fileName === "string") {
      return `${sharerEmail} shared "${fileName}" with you`
    }
  }

  return "New notification"
}
