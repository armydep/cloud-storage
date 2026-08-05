export async function calculateSha256(file: File): Promise<string> {
  const buffer = await file.arrayBuffer()
  const hashBuffer = await crypto.subtle.digest("SHA-256", buffer)
  const hashBytes = Array.from(new Uint8Array(hashBuffer))

  return hashBytes.map((byte) => byte.toString(16).padStart(2, "0")).join("")
}
