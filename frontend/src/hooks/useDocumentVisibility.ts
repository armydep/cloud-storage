import { useEffect, useState } from "react"

function isVisible() {
  return (
    typeof document === "undefined" || document.visibilityState === "visible"
  )
}

/** Tracks tab visibility so polling can pause while the tab is hidden. */
export function useDocumentVisibility(): boolean {
  const [visible, setVisible] = useState(isVisible)

  useEffect(() => {
    const handleChange = () => setVisible(isVisible())
    document.addEventListener("visibilitychange", handleChange)
    return () => document.removeEventListener("visibilitychange", handleChange)
  }, [])

  return visible
}
