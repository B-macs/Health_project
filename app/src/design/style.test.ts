// Every colour comes from the tokens (rebuild Phase 3): no screen file or stylesheet
// writes a colour of its own, and the stylesheet writes no size of its own either.
// tokens.ts is the one place colours and sizes are written.
import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'

const SRC = join(__dirname, '..')
const COLOUR = /#[0-9a-fA-F]{3,8}\b|\brgba?\(|\bhsla?\(/

function files(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name)
    return statSync(path).isDirectory() ? files(path) : [path]
  })
}

const SCREEN_FILES = files(SRC).filter(
  (f) => /\.(tsx|css)$/.test(f) && !f.endsWith('tokens.ts') && !f.includes(`${join('mock', '')}`),
)

describe('colours and sizes come from the tokens', () => {
  it.each(SCREEN_FILES.map((f) => [f.slice(SRC.length + 1), f]))('%s writes no colour', (_name, path) => {
    const text = readFileSync(path, 'utf-8')
      .split('\n')
      .filter((line) => !line.trim().startsWith('//') && !line.trim().startsWith('*'))
      .join('\n')
    expect(text).not.toMatch(COLOUR)
  })

  it('the stylesheet writes no px, rem or em size outside the base font size', () => {
    const css = readFileSync(join(SRC, 'bakeoff', 'bakeoff.css'), 'utf-8')
    const declarations = css
      .replace(/\/\*[\s\S]*?\*\//g, '')
      .split('\n')
      .filter((line) => /:\s/.test(line) && !/^\s*font-size:\s*17px;/.test(line))
    const sized = declarations.filter((line) => /\d(px|rem|em)\b/.test(line))
    expect(sized).toEqual([])
  })
})
