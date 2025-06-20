export function buildUrl(base: string, patch: string, params: Record<string, string | undefined> = {}) {
  const searchParams = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined) {
      searchParams.append(key, value)
    }
  }
  return `${base}/${patch}?${searchParams.toString()}`
}