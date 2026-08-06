import { expect, test } from "@playwright/test"

const sharedFiles = {
  data: [
    {
      id: "00000000-0000-0000-0000-000000000030",
      name: "quarterly-report.pdf",
      mime_type: "application/pdf",
      category: "document",
      size_bytes: 2048,
      owner_email: "owner@example.com",
      shared_at: "2026-08-06T12:00:00Z",
    },
  ],
  count: 1,
}

test.beforeEach(async ({ page }) => {
  await page.route("**/api/v1/users/me", async (route) => {
    await route.fulfill({
      json: {
        id: "00000000-0000-0000-0000-000000000010",
        email: "recipient@example.com",
        is_active: true,
        is_superuser: false,
        full_name: "File Recipient",
      },
    })
  })
})

test("Shared with me navigation shows shared file metadata", async ({
  page,
}) => {
  await page.route("**/api/v1/files/shared-with-me", async (route) => {
    await route.fulfill({ json: sharedFiles })
  })

  await page.goto("/files")
  await page.getByRole("link", { name: "Shared with me" }).click()

  await expect(page).toHaveURL(/\/shared-with-me$/)
  await expect(
    page.getByRole("heading", { name: "Shared with me" }),
  ).toBeVisible()
  const row = page.getByRole("row").filter({ hasText: "quarterly-report.pdf" })
  await expect(row.getByText("owner@example.com")).toBeVisible()
  await expect(row.getByText("application/pdf")).toBeVisible()
  await expect(
    row.getByRole("button", { name: "Download quarterly-report.pdf" }),
  ).toBeVisible()
  await expect(row.getByRole("button", { name: /share/i })).toHaveCount(0)
})

test("Shared with me shows an empty state", async ({ page }) => {
  await page.route("**/api/v1/files/shared-with-me", async (route) => {
    await route.fulfill({ json: { data: [], count: 0 } })
  })

  await page.goto("/shared-with-me")

  await expect(page.getByText("No files shared with you")).toBeVisible()
  await expect(
    page.getByText("Files other users share with you will appear here."),
  ).toBeVisible()
})

test("Shared with me displays a loading state", async ({ page }) => {
  let releaseResponse: (() => void) | undefined
  const responseGate = new Promise<void>((resolve) => {
    releaseResponse = resolve
  })
  await page.route("**/api/v1/files/shared-with-me", async (route) => {
    await responseGate
    await route.fulfill({ json: sharedFiles })
  })

  await page.goto("/shared-with-me")
  await expect(page.getByRole("status")).toHaveText("Loading shared files…")
  releaseResponse?.()
  await expect(
    page.getByText("quarterly-report.pdf", { exact: true }),
  ).toBeVisible()
})

test("Shared file download calls presign-download", async ({ page }) => {
  let presignDownloadCalled = false
  await page.route("**/api/v1/files/shared-with-me", async (route) => {
    await route.fulfill({ json: sharedFiles })
  })
  await page.route("**/api/v1/files/*/presign-download", async (route) => {
    presignDownloadCalled = true
    await route.fulfill({
      json: {
        download_url: "http://localhost:5173/downloads/quarterly-report.pdf",
        method: "GET",
        expires_in: 900,
      },
    })
  })
  await page.route("**/downloads/quarterly-report.pdf", async (route) => {
    await route.fulfill({ body: "report", contentType: "application/pdf" })
  })

  await page.goto("/shared-with-me")
  await page
    .getByRole("button", { name: "Download quarterly-report.pdf" })
    .click()

  await expect.poll(() => presignDownloadCalled).toBe(true)
})
