// The screen stays on during a session (T88): the lock is asked for at the start, asked
// for again when the app comes back to the front (iOS lets go of it in the background),
// and given back when the session ends.
import { describe, expect, it } from 'vitest'
import { holdScreen, type WakeLockHost } from './wakelock'

class Sentinel extends EventTarget {
  released = false
  async release(): Promise<void> {
    this.released = true
    this.dispatchEvent(new Event('release'))
  }
}

class Page extends EventTarget {
  visibilityState: DocumentVisibilityState = 'visible'
}

function host() {
  const asked: Sentinel[] = []
  const nav: WakeLockHost = {
    wakeLock: {
      request: async () => {
        const s = new Sentinel()
        asked.push(s)
        return s as unknown as WakeLockSentinel
      },
    },
  }
  return { nav, asked }
}

const settle = () => new Promise((resolve) => setTimeout(resolve, 0))

describe('the screen wake lock', () => {
  it('is held from the start, and given back at the end', async () => {
    const { nav, asked } = host()
    const heard: boolean[] = []
    const stop = holdScreen(nav, new Page() as unknown as Document, (held) => heard.push(held))
    await settle()
    expect(asked).toHaveLength(1)
    expect(heard).toEqual([true])
    stop()
    await settle()
    expect(asked[0].released).toBe(true)
    expect(heard).toEqual([true, false])
  })

  it('is asked for again when the app comes back to the front', async () => {
    const { nav, asked } = host()
    const page = new Page()
    const stop = holdScreen(nav, page as unknown as Document, () => undefined)
    await settle()
    page.visibilityState = 'hidden'
    page.dispatchEvent(new Event('visibilitychange'))
    await settle()
    expect(asked).toHaveLength(1)
    page.visibilityState = 'visible'
    page.dispatchEvent(new Event('visibilitychange'))
    await settle()
    expect(asked).toHaveLength(2)
    stop()
  })

  it('without the API, nothing happens and nothing breaks', async () => {
    const heard: boolean[] = []
    const stop = holdScreen({}, new Page() as unknown as Document, (held) => heard.push(held))
    await settle()
    expect(heard).toEqual([])
    stop()
  })

  it('a refused request says the lock is not held', async () => {
    const heard: boolean[] = []
    const nav: WakeLockHost = { wakeLock: { request: async () => { throw new Error('NotAllowedError') } } }
    holdScreen(nav, new Page() as unknown as Document, (held) => heard.push(held))
    await settle()
    expect(heard).toEqual([false])
  })
})
