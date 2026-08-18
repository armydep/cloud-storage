import { expect, test } from "@playwright/test"

test("routes browser search API requests to the search service", async ({
  page,
}) => {
  const apiUrl = process.env.VITE_API_URL
  if (!apiUrl) throw new Error("VITE_API_URL is required")

  await page.goto("/")
  await expect
    .poll(async () => {
      return page.evaluate(async (origin) => {
        try {
          const response = await fetch(`${origin}/api/v1/search/openapi.json`)
          if (!response.ok) return { status: response.status }

          const document = await response.json()
          return {
            status: response.status,
            title: document.info.title,
            hasFilesRoute: "/api/v1/search/files" in document.paths,
          }
        } catch (error) {
          return { error: String(error) }
        }
      }, apiUrl)
    })
    .toEqual({
      status: 200,
      title: "Cloud File Storage Search",
      hasFilesRoute: true,
    })
})
