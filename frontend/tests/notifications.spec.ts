import { expect, type Page, test } from "@playwright/test"

type Notification = {
  id: string
  event_type: string
  payload: Record<string, unknown>
  created_at: string
  read_at: string | null
}

function fileSharedNotification(
  overrides: Partial<Notification> = {},
): Notification {
  return {
    id: "00000000-0000-0000-0000-000000000101",
    event_type: "file_shared",
    payload: {
      file_id: "00000000-0000-0000-0000-000000000201",
      file_name: "report.pdf",
      recipient_id: "00000000-0000-0000-0000-000000000010",
      recipient_email: "recipient@example.com",
      sharer_email: "alice@example.com",
    },
    created_at: "2026-08-10T12:00:00Z",
    read_at: null,
    ...overrides,
  }
}

// The list endpoint takes a query string (limit/cursor/unread_only), so the
// glob form used elsewhere in this suite (e.g. "**/shared-with-me") would
// also swallow the unrelated /unread-count, /read-all and /{id}/read routes.
// A regex anchored on the exact path avoids that collision.
const notificationsListPattern = /\/api\/v1\/notifications(\?.*)?$/

async function mockUnreadCount(page: Page, count: number) {
  await page.route("**/api/v1/notifications/unread-count", async (route) => {
    await route.fulfill({ json: { count } })
  })
}

test.describe("Notification bell", () => {
  test("shows the unread count and hides the badge at zero", async ({
    page,
  }) => {
    await mockUnreadCount(page, 3)
    await page.route(notificationsListPattern, async (route) => {
      await route.fulfill({ json: { data: [], next_cursor: null } })
    })

    await page.goto("/")
    const bell = page.getByRole("button", { name: "Notifications" })
    await expect(bell.locator('[data-slot="badge"]')).toHaveText("3")

    await mockUnreadCount(page, 0)
    await page.goto("/")
    const freshBell = page.getByRole("button", { name: "Notifications" })
    await expect(freshBell.locator('[data-slot="badge"]')).toHaveCount(0)
  })

  test("opening the feed does not mark notifications read", async ({
    page,
  }) => {
    let readCalled = false
    let readAllCalled = false
    await mockUnreadCount(page, 2)
    await page.route(notificationsListPattern, async (route) => {
      await route.fulfill({
        json: {
          data: [
            fileSharedNotification({ id: "notif-1" }),
            fileSharedNotification({
              id: "notif-2",
              payload: {
                file_id: "file-2",
                file_name: "budget.xlsx",
                recipient_id: "recipient-id",
                recipient_email: "recipient@example.com",
                sharer_email: "bob@example.com",
              },
            }),
          ],
          next_cursor: null,
        },
      })
    })
    await page.route("**/api/v1/notifications/*/read", async (route) => {
      readCalled = true
      await route.fulfill({ json: fileSharedNotification() })
    })
    await page.route("**/api/v1/notifications/read-all", async (route) => {
      readAllCalled = true
      await route.fulfill({ status: 204, body: "" })
    })

    await page.goto("/")
    await page.getByRole("button", { name: "Notifications" }).click()

    const sheet = page.getByRole("dialog")
    await expect(
      sheet.getByText('alice@example.com shared "report.pdf" with you'),
    ).toBeVisible()
    await expect(
      sheet.getByText('bob@example.com shared "budget.xlsx" with you'),
    ).toBeVisible()

    expect(readCalled).toBe(false)
    expect(readAllCalled).toBe(false)
    await expect(
      page
        .getByRole("button", { name: "Notifications" })
        .locator('[data-slot="badge"]'),
    ).toHaveText("2")
  })

  test("marking one notification read decrements the badge and leaves the sibling unread", async ({
    page,
  }) => {
    // A single stateful handler per route, flipped by the mutation itself —
    // re-registering page.route() *after* the click would race the
    // mutation's own invalidation-triggered refetch, which can fire before
    // the test gets a chance to swap the mock in.
    let notif1Read = false
    await page.route("**/api/v1/notifications/unread-count", async (route) => {
      await route.fulfill({ json: { count: notif1Read ? 1 : 2 } })
    })
    await page.route(notificationsListPattern, async (route) => {
      await route.fulfill({
        json: {
          data: [
            fileSharedNotification({
              id: "notif-1",
              read_at: notif1Read ? "2026-08-10T12:05:00Z" : null,
            }),
            fileSharedNotification({
              id: "notif-2",
              payload: {
                file_id: "file-2",
                file_name: "budget.xlsx",
                recipient_id: "recipient-id",
                recipient_email: "recipient@example.com",
                sharer_email: "bob@example.com",
              },
            }),
          ],
          next_cursor: null,
        },
      })
    })
    await page.route("**/api/v1/notifications/notif-1/read", async (route) => {
      notif1Read = true
      await route.fulfill({
        json: fileSharedNotification({
          id: "notif-1",
          read_at: "2026-08-10T12:05:00Z",
        }),
      })
    })

    await page.goto("/")
    await page.getByRole("button", { name: "Notifications" }).click()
    const sheet = page.getByRole("dialog")

    await sheet.getByRole("button", { name: "Mark read" }).first().click()

    await expect(
      page
        .getByRole("button", { name: "Notifications" })
        .locator('[data-slot="badge"]'),
    ).toHaveText("1")
    await expect(sheet.getByRole("button", { name: "Mark read" })).toHaveCount(
      1,
    )
    await expect(
      sheet.getByText('bob@example.com shared "budget.xlsx" with you'),
    ).toBeVisible()
  })

  test("mark all read clears the badge", async ({ page }) => {
    let markedAll = false
    await page.route("**/api/v1/notifications/unread-count", async (route) => {
      await route.fulfill({ json: { count: markedAll ? 0 : 2 } })
    })
    await page.route(notificationsListPattern, async (route) => {
      await route.fulfill({
        json: {
          data: [
            fileSharedNotification({
              id: "notif-1",
              read_at: markedAll ? "2026-08-10T12:05:00Z" : null,
            }),
            fileSharedNotification({
              id: "notif-2",
              read_at: markedAll ? "2026-08-10T12:05:00Z" : null,
              payload: {
                file_id: "file-2",
                file_name: "budget.xlsx",
                recipient_id: "recipient-id",
                recipient_email: "recipient@example.com",
                sharer_email: "bob@example.com",
              },
            }),
          ],
          next_cursor: null,
        },
      })
    })
    await page.route("**/api/v1/notifications/read-all", async (route) => {
      markedAll = true
      await route.fulfill({ status: 204, body: "" })
    })

    await page.goto("/")
    await page.getByRole("button", { name: "Notifications" }).click()
    const sheet = page.getByRole("dialog")

    await sheet.getByRole("button", { name: "Mark all read" }).click()

    await expect(
      page
        .getByRole("button", { name: "Notifications" })
        .locator('[data-slot="badge"]'),
    ).toHaveCount(0)
    await expect(sheet.getByRole("button", { name: "Mark read" })).toHaveCount(
      0,
    )
  })

  test("loads more notifications by cursor without duplicating entries", async ({
    page,
  }) => {
    await mockUnreadCount(page, 3)
    await page.route(notificationsListPattern, async (route) => {
      const url = new URL(route.request().url())
      const cursor = url.searchParams.get("cursor")
      if (!cursor) {
        await route.fulfill({
          json: {
            data: [
              fileSharedNotification({ id: "notif-1" }),
              fileSharedNotification({ id: "notif-2" }),
            ],
            next_cursor: "page-2-cursor",
          },
        })
        return
      }
      expect(cursor).toBe("page-2-cursor")
      await route.fulfill({
        json: {
          data: [fileSharedNotification({ id: "notif-3" })],
          next_cursor: null,
        },
      })
    })

    await page.goto("/")
    await page.getByRole("button", { name: "Notifications" }).click()
    const sheet = page.getByRole("dialog")

    await expect(
      sheet.getByText('alice@example.com shared "report.pdf" with you'),
    ).toHaveCount(2)
    await sheet.getByRole("button", { name: "Load more" }).click()

    await expect(
      sheet.getByText('alice@example.com shared "report.pdf" with you'),
    ).toHaveCount(3)
    await expect(sheet.getByRole("button", { name: "Load more" })).toHaveCount(
      0,
    )
  })
})
