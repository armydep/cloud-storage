import { sha256 } from "js-sha256"

export async function calculateSha256(file: File): Promise<string> {
  const chunkSize = 64 * 1024
  let offset = 0
  const hash = sha256.create()

  while (offset < file.size) {
    const chunk = file.slice(offset, offset + chunkSize)
    const buffer = await chunk.arrayBuffer()
    hash.update(new Uint8Array(buffer))
    offset += chunkSize
  }

  return hash.hex()
}
