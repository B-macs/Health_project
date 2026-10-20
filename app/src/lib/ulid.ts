// ULIDs (from Lauscher's app/src/lib/ulid.ts): 48 bits of Unix milliseconds, then 80
// random bits, in Crockford base32. The phone mints every write's id with it (rebuild rule
// 4: a save sent three times stores one), and the outbox sends in id order.
const CROCKFORD = '0123456789ABCDEFGHJKMNPQRSTVWXYZ'

export function ulid(ms: number = Date.now()): string {
  let time = ''
  let rest = ms
  for (let i = 0; i < 10; i++) {
    time = CROCKFORD[rest % 32] + time
    rest = Math.floor(rest / 32)
  }
  const random = crypto.getRandomValues(new Uint8Array(16))
  let tail = ''
  for (let i = 0; i < 16; i++) tail += CROCKFORD[random[i] % 32]
  return time + tail
}

/** Milliseconds since the epoch from a ULID's first 10 characters. */
export function ulidTime(id: string): number {
  let ms = 0
  for (const char of id.slice(0, 10)) ms = ms * 32 + CROCKFORD.indexOf(char)
  return ms
}

export const ULID = /^[0-9A-HJKMNP-TV-Z]{26}$/
