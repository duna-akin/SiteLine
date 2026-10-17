/** Read a theme token's resolved value (e.g. "--glow" → "#dbeec2") for canvas-based components that need a hex string. */
export function token(name: string): string {
  if (typeof window === 'undefined') return ''
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim()
}
