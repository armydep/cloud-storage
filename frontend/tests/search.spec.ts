import { expect, test } from "@playwright/test"

const searchResult = {
  id: "00000000-0000-0000-0000-000000000051",
  name: "quarterly-report.pdf",
  folder_path: "root.documents.reports",
  mime_type: "application/pdf",
  category: "document",
  size_bytes: 2048,
  created_at: "2026-08-08T10:30:00Z",
}

const emptyFolder = {
  id: "00000000-0000-0000-0000-000000000050",
  owner_id: "00000000-0000-0000-0000-000000000010",
  parent_id: null,
  path: "root.documents",
  name: "documents",
  contents: [],
}

const formatTestDate = (value: string) =>
  new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value))

test.beforeEach(async ({ page }) => {
  await page.route("**/api/v1/users/me", async (route) => {
    await route.fulfill({
      json: {
        id: "00000000-0000-0000-0000-000000000010",
        email: "owner@example.com",
        is_active: true,
        is_superuser: false,
        full_name: "File Owner",
      },
    })
  })
  await page.route("**/api/v1/files?**", async (route) => {
    await route.fulfill({ json: emptyFolder })
  })
})

test("searches the current folder after a debounce and opens a result", async ({
  page,
}) => {
  const requests: URL[] = []
  let releaseSearch: (() => void) | undefined
  const searchGate = new Promise<void>((resolve) => {
    releaseSearch = resolve
  })
  let presignDownloadCalled = false

  await page.route("**/api/v1/search/files?**", async (route) => {
    requests.push(new URL(route.request().url()))
    await searchGate
    await route.fulfill({
      json: { results: [searchResult], next_cursor: null },
    })
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

  await page.goto("/files?path=root.documents")
  await page
    .getByRole("searchbox", { name: "Search files in root.documents" })
    .pressSequentially("quarterly", { delay: 25 })

  await expect(page.getByRole("status")).toHaveText("Searching files…")
  await expect.poll(() => requests.length).toBe(1)
  releaseSearch?.()

  const request = requests[0]
  expect(request.searchParams.get("folder_path")).toBe("root.documents")
  expect(request.searchParams.get("q")).toBe("quarterly")
  expect(request.searchParams.get("limit")).toBe("25")

  const resultRow = page
    .getByRole("row")
    .filter({ hasText: "quarterly-report.pdf" })
  await expect(resultRow.getByText("root.documents.reports")).toBeVisible()
  await expect(resultRow.getByText("2K")).toBeVisible()
  await expect(
    resultRow.getByText(formatTestDate(searchResult.created_at)),
  ).toBeVisible()
  await resultRow.getByRole("button", { name: "Open file actions" }).click()
  await page.getByRole("menuitem", { name: "Download" }).click()
  await expect.poll(() => presignDownloadCalled).toBe(true)
})

test("filters by category and passes the opaque cursor back unchanged", async ({
  page,
}) => {
  const opaqueCursor = "opaque+cursor=/with-symbols"
  const requests: URL[] = []

  await page.route("**/api/v1/search/files?**", async (route) => {
    const url = new URL(route.request().url())
    requests.push(url)

    if (url.searchParams.has("cursor")) {
      await route.fulfill({
        json: {
          results: [
            {
              ...searchResult,
              id: "00000000-0000-0000-0000-000000000052",
              name: "annual-report.pdf",
            },
          ],
          next_cursor: null,
        },
      })
      return
    }

    await route.fulfill({
      json: { results: [searchResult], next_cursor: opaqueCursor },
    })
  })

  await page.goto("/files?path=root.documents")
  await page.getByRole("combobox", { name: "File category" }).click()
  await page.getByRole("option", { name: "Document" }).click()

  await expect(page.getByText("quarterly-report.pdf")).toBeVisible()
  expect(requests[0].searchParams.get("folder_path")).toBe("root.documents")
  expect(requests[0].searchParams.get("category")).toBe("document")

  await page.getByRole("button", { name: "Load more" }).click()
  await expect(page.getByText("annual-report.pdf")).toBeVisible()
  expect(requests[1].searchParams.get("cursor")).toBe(opaqueCursor)
  expect(requests[1].searchParams.get("folder_path")).toBe("root.documents")
})

test("shows a distinct empty search state", async ({ page }) => {
  await page.route("**/api/v1/search/files?**", async (route) => {
    await route.fulfill({ json: { results: [], next_cursor: null } })
  })

  await page.goto("/files?path=root.documents")
  await page
    .getByRole("searchbox", { name: "Search files in root.documents" })
    .fill("missing")

  await expect(page.getByText("No matching files")).toBeVisible()
  await expect(page.getByText("Search is unavailable")).toHaveCount(0)
})

test("shows an error instead of an empty state when search is unavailable", async ({
  page,
}) => {
  await page.route("**/api/v1/search/files?**", async (route) => {
    await route.fulfill({
      status: 503,
      json: { detail: "Search index unavailable" },
    })
  })

  await page.goto("/files?path=root.documents")
  await page
    .getByRole("searchbox", { name: "Search files in root.documents" })
    .fill("report")

  await expect(page.getByRole("alert")).toContainText("Search is unavailable")
  await expect(page.getByText("No matching files")).toHaveCount(0)
})
