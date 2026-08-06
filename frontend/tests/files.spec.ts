import { expect, test } from "@playwright/test"

const rootFolder = {
  id: "00000000-0000-0000-0000-000000000001",
  owner_id: "00000000-0000-0000-0000-000000000010",
  parent_id: null,
  path: "root",
  name: "root",
  contents: [
    {
      id: "00000000-0000-0000-0000-000000000002",
      name: "Documents",
      type: "folder",
      path: "root.documents",
    },
    {
      id: "00000000-0000-0000-0000-000000000003",
      name: "welcome.txt",
      type: "file",
      mime_type: "text/plain",
      category: "document",
      blob_hash:
        "1111111111111111111111111111111111111111111111111111111111111111",
      size_bytes: 128,
    },
  ],
}

const documentsFolder = {
  id: "00000000-0000-0000-0000-000000000002",
  owner_id: "00000000-0000-0000-0000-000000000010",
  parent_id: "00000000-0000-0000-0000-000000000001",
  path: "root.documents",
  name: "Documents",
  contents: [
    {
      id: "00000000-0000-0000-0000-000000000004",
      name: "requirements.pdf",
      type: "file",
      mime_type: "application/pdf",
      category: "document",
      blob_hash:
        "2222222222222222222222222222222222222222222222222222222222222222",
      size_bytes: 84210,
    },
  ],
}

const emptyFolder = {
  id: "00000000-0000-0000-0000-000000000005",
  owner_id: "00000000-0000-0000-0000-000000000010",
  parent_id: "00000000-0000-0000-0000-000000000001",
  path: "root.empty_folder",
  name: "Empty Folder",
  contents: [],
}

test.beforeEach(async ({ page }) => {
  await page.route("**/api/v1/files?**", async (route) => {
    const url = new URL(route.request().url())
    const path = url.searchParams.get("path") || "root"

    if (path === "root.documents") {
      await route.fulfill({ json: documentsFolder })
      return
    }

    if (path === "root.empty_folder") {
      await route.fulfill({ json: emptyFolder })
      return
    }

    await route.fulfill({ json: rootFolder })
  })
})

test("Files page shows current path and upload button", async ({ page }) => {
  await page.goto("/files")

  await expect(page.getByRole("heading", { name: "Files" })).toBeVisible()
  await expect(page.getByText("Current path:")).toBeVisible()
  await expect(page.getByRole("button", { name: "root" })).toBeVisible()
  await expect(page.getByRole("button", { name: "Upload" })).toBeVisible()
  await expect(page.getByRole("button", { name: "New folder" })).toBeVisible()
})

test("Create folder submits the current path and refreshes the listing", async ({
  page,
}) => {
  let requestBody: unknown
  let folderCreated = false

  await page.route("**/api/v1/files/folders", async (route) => {
    requestBody = route.request().postDataJSON()
    folderCreated = true
    await route.fulfill({
      status: 201,
      json: {
        id: "00000000-0000-0000-0000-000000000006",
        owner_id: rootFolder.owner_id,
        parent_id: rootFolder.id,
        path: "root.project_files",
        name: "Project Files",
      },
    })
  })
  await page.route("**/api/v1/files?**", async (route) => {
    await route.fulfill({
      json: folderCreated
        ? {
            ...rootFolder,
            contents: [
              ...rootFolder.contents,
              {
                id: "00000000-0000-0000-0000-000000000006",
                name: "Project Files",
                type: "folder",
                path: "root.project_files",
              },
            ],
          }
        : rootFolder,
    })
  })

  await page.goto("/files")
  await page.getByRole("button", { name: "New folder" }).click()
  await page.getByLabel("Folder name").fill("Project Files")
  await page.getByRole("button", { name: "Create", exact: true }).click()

  await expect(page.getByText("Folder created successfully")).toBeVisible()
  await expect(
    page.getByRole("button", { name: "Project Files" }),
  ).toBeVisible()
  expect(requestBody).toEqual({
    parent_path: "root",
    name: "Project Files",
  })
})

test("Create folder validates a blank name", async ({ page }) => {
  await page.goto("/files")
  await page.getByRole("button", { name: "New folder" }).click()
  await page.getByRole("button", { name: "Create", exact: true }).click()

  await expect(page.getByText("Folder name is required")).toBeVisible()
})

test("Create folder shows a duplicate-name error", async ({ page }) => {
  await page.route("**/api/v1/files/folders", async (route) => {
    await route.fulfill({
      status: 409,
      json: { detail: "Folder name already exists" },
    })
  })

  await page.goto("/files")
  await page.getByRole("button", { name: "New folder" }).click()
  await page.getByLabel("Folder name").fill("Documents")
  await page.getByRole("button", { name: "Create", exact: true }).click()

  await expect(
    page.getByText("A folder with this name already exists in this folder."),
  ).toBeVisible()
})

test("Folder row click navigates to child folder path", async ({ page }) => {
  await page.goto("/files")

  await page.getByRole("button", { name: "Documents" }).click()

  await expect(page).toHaveURL(/\/files\?path=root\.documents/)
  await expect(page.getByRole("button", { name: "documents" })).toBeVisible()
  await expect(page.getByText("requirements.pdf")).toBeVisible()
})

test("Empty folder shows empty state", async ({ page }) => {
  await page.goto("/files?path=root.empty_folder")

  await expect(page.getByText("This folder is empty")).toBeVisible()
  await expect(
    page.getByText("Files and folders you add later will appear here."),
  ).toBeVisible()
})

test("File rows show download action and folder rows do not", async ({
  page,
}) => {
  await page.goto("/files")

  const fileRow = page.getByRole("row").filter({ hasText: "welcome.txt" })
  const folderRow = page.getByRole("row").filter({ hasText: "Documents" })

  await expect(
    fileRow.getByRole("button", { name: "Open file actions" }),
  ).toBeVisible()
  await expect(
    folderRow.getByRole("button", { name: "Open file actions" }),
  ).toHaveCount(0)
})

test("Download action calls presign-download", async ({ page }) => {
  let presignDownloadCalled = false

  await page.route("**/api/v1/files/*/presign-download", async (route) => {
    presignDownloadCalled = true
    await route.fulfill({
      json: {
        download_url: "http://localhost:5173/downloads/welcome.txt",
        method: "GET",
        expires_in: 900,
      },
    })
  })
  await page.route("**/downloads/welcome.txt", async (route) => {
    await route.fulfill({
      body: "hello",
      contentType: "text/plain",
    })
  })

  await page.goto("/files")

  const fileRow = page.getByRole("row").filter({ hasText: "welcome.txt" })
  await fileRow.getByRole("button", { name: "Open file actions" }).click()
  await page.getByRole("menuitem", { name: "Download" }).click()

  await expect.poll(() => presignDownloadCalled).toBe(true)
})
