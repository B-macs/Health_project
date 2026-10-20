// Every colour comes from the tokens (rebuild Phase 3): no screen file or stylesheet
// writes a colour of its own, and the stylesheet writes no size of its own either.
// tokens.ts is the one place colours and sizes are written. The files are read through
// Vite's own loader (?raw), so the test needs no Node types.
import { describe, expect, it } from 'vitest'
import stylesheet from '../ui/app.css?raw'

const COLOUR = /#[0-9a-fA-F]{3,8}\b|\brgba?\(|\bhsla?\(/

const SOURCES = import.meta.glob(['../**/*.tsx', '../**/*.css'], {
  query: '?raw',
  import: 'default',
  eager: true,
}) as Record<string, string>

function code(text: string): string {
  return text
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .split('\n')
    .filter((line) => !line.trim().startsWith('//'))
    .join('\n')
}

describe('colours and sizes come from the tokens', () => {
  it('finds the screen files', () => {
    expect(Object.keys(SOURCES).length).toBeGreaterThan(5)
  })

  it.each(Object.entries(SOURCES))('%s writes no colour', (_name, text) => {
    expect(code(text)).not.toMatch(COLOUR)
  })

  it('the stylesheet writes no px, rem or em size outside the base font size', () => {
    const sized = code(stylesheet)
      .split('\n')
      .filter((line) => /:\s/.test(line) && !/^\s*font-size:\s*17px;/.test(line))
      .filter((line) => /\d(px|rem|em)\b/.test(line))
    expect(sized).toEqual([])
  })
})
