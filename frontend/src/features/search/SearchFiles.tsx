import { useInfiniteQuery } from "@tanstack/react-query"
import { CircleAlert, Loader2, Search } from "lucide-react"
import { type ReactNode, useEffect, useMemo, useState } from "react"

import { DataTable } from "@/components/Common/DataTable"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { type FileCategory, SearchService } from "@/search-client"

import { getSearchColumns } from "./columns"

const SEARCH_DEBOUNCE_MS = 300
const SEARCH_PAGE_SIZE = 25
const ALL_CATEGORIES = "all"
const FILE_CATEGORIES: FileCategory[] = [
  "image",
  "video",
  "audio",
  "document",
  "spreadsheet",
  "archive",
  "other",
]

type CategoryFilter = FileCategory | typeof ALL_CATEGORIES

function useDebouncedValue<T>(value: T, delay: number): T {
  const [debouncedValue, setDebouncedValue] = useState(value)

  useEffect(() => {
    const timeout = window.setTimeout(() => setDebouncedValue(value), delay)
    return () => window.clearTimeout(timeout)
  }, [delay, value])

  return debouncedValue
}

export default function SearchFiles({
  children,
  currentPath,
}: {
  children: ReactNode
  currentPath: string
}) {
  const [searchText, setSearchText] = useState("")
  const [category, setCategory] = useState<CategoryFilter>(ALL_CATEGORIES)
  const normalizedSearchText = searchText.trim()
  const debouncedSearchText = useDebouncedValue(
    normalizedSearchText,
    SEARCH_DEBOUNCE_MS,
  )
  const isDebouncing = normalizedSearchText !== debouncedSearchText
  const isSearchActive =
    normalizedSearchText.length > 0 || category !== ALL_CATEGORIES

  const searchQuery = useInfiniteQuery({
    queryKey: ["file-search", currentPath, debouncedSearchText, category],
    queryFn: ({ pageParam }) =>
      SearchService.filesApiV1SearchFilesGet({
        folderPath: currentPath,
        q: debouncedSearchText || undefined,
        category: category === ALL_CATEGORIES ? undefined : category,
        limit: SEARCH_PAGE_SIZE,
        cursor: pageParam,
      }),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (lastPage) => lastPage.next_cursor ?? undefined,
    enabled: isSearchActive && !isDebouncing,
    retry: false,
  })

  const results = useMemo(
    () => searchQuery.data?.pages.flatMap((page) => page.results ?? []) ?? [],
    [searchQuery.data],
  )
  const columns = useMemo(() => getSearchColumns(), [])
  const isLoading = isSearchActive && (isDebouncing || searchQuery.isPending)

  return (
    <section className="flex flex-col gap-4" aria-label="Search files">
      <div className="flex flex-col gap-3 sm:flex-row">
        <div className="relative flex-1">
          <Search
            aria-hidden="true"
            className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
          />
          <Input
            aria-label={`Search files in ${currentPath}`}
            className="pl-9"
            type="search"
            value={searchText}
            placeholder={`Search in ${currentPath}`}
            onChange={(event) => setSearchText(event.target.value)}
          />
        </div>
        <Select
          value={category}
          onValueChange={(value) => setCategory(value as CategoryFilter)}
        >
          <SelectTrigger aria-label="File category" className="w-full sm:w-48">
            <SelectValue placeholder="All categories" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL_CATEGORIES}>All categories</SelectItem>
            {FILE_CATEGORIES.map((fileCategory) => (
              <SelectItem key={fileCategory} value={fileCategory}>
                {fileCategory.charAt(0).toUpperCase() + fileCategory.slice(1)}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {!isSearchActive ? (
        children
      ) : isLoading ? (
        <div
          className="flex min-h-40 items-center justify-center gap-2 text-sm text-muted-foreground"
          role="status"
        >
          <Loader2 className="size-4 animate-spin" />
          Searching files…
        </div>
      ) : searchQuery.isError ? (
        <div
          className="flex min-h-40 flex-col items-center justify-center gap-3 rounded-md border border-destructive/50 p-6 text-center"
          role="alert"
        >
          <CircleAlert className="size-8 text-destructive" />
          <div>
            <h2 className="font-semibold text-destructive">
              Search is unavailable
            </h2>
            <p className="text-sm text-muted-foreground">
              Your files could not be searched. Try again shortly.
            </p>
          </div>
          <Button
            type="button"
            variant="outline"
            disabled={searchQuery.isFetching}
            onClick={() => searchQuery.refetch()}
          >
            {searchQuery.isFetching ? "Retrying…" : "Retry"}
          </Button>
        </div>
      ) : results.length === 0 ? (
        <div className="flex min-h-40 flex-col items-center justify-center gap-2 rounded-md border p-6 text-center">
          <Search className="size-8 text-muted-foreground" />
          <h2 className="font-semibold">No matching files</h2>
          <p className="text-sm text-muted-foreground">
            Try a different name or category in this folder.
          </p>
        </div>
      ) : (
        <div className="flex flex-col gap-4">
          <p className="text-sm text-muted-foreground" aria-live="polite">
            Showing {results.length} search{" "}
            {results.length === 1 ? "result" : "results"}
            {` in ${currentPath}`}
          </p>
          <DataTable
            columns={columns}
            data={results}
            enablePagination={false}
          />
          {searchQuery.hasNextPage && (
            <Button
              type="button"
              variant="outline"
              className="self-center"
              disabled={searchQuery.isFetchingNextPage}
              onClick={() => searchQuery.fetchNextPage()}
            >
              {searchQuery.isFetchingNextPage ? (
                <>
                  <Loader2 className="animate-spin" />
                  Loading more…
                </>
              ) : (
                "Load more"
              )}
            </Button>
          )}
        </div>
      )}
    </section>
  )
}
