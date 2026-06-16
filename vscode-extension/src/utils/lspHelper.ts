export function isSourceFile(path: string): boolean {
  return /\.(py|java|ts|tsx|go|rs)$/.test(path);
}
