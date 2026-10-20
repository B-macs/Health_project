// The phone's storage for this app (rebuild Phase 4): whether the browser keeps it under
// storage pressure (persist), and how much is used of how much. Settings shows both as they
// are; Safari may answer "not kept" for a Home Screen app, and that is shown too.
import { S } from '../strings'

export interface StorageInfo {
  persisted: boolean | null
  usage: number | null
  quota: number | null
}

export async function askToKeep(): Promise<boolean | null> {
  try {
    return (await navigator.storage?.persist?.()) ?? null
  } catch {
    return null
  }
}

export async function storageInfo(): Promise<StorageInfo> {
  let persisted: boolean | null = null
  let usage: number | null = null
  let quota: number | null = null
  try {
    persisted = (await navigator.storage?.persisted?.()) ?? null
  } catch {
    persisted = null
  }
  try {
    const estimate = await navigator.storage?.estimate?.()
    usage = estimate?.usage ?? null
    quota = estimate?.quota ?? null
  } catch {
    usage = null
  }
  return { persisted, usage, quota }
}

/** 1234567 -> "1.2 MB" (decimal units, as iOS Settings shows them). */
export function formatBytes(n: number | null): string {
  if (n == null || !Number.isFinite(n)) return '—'
  const units = S.units.bytes
  let value = n
  let i = 0
  while (value >= 1000 && i < units.length - 1) {
    value /= 1000
    i += 1
  }
  return `${i > 0 && value < 10 ? value.toFixed(1) : Math.round(value)} ${units[i]}`
}
