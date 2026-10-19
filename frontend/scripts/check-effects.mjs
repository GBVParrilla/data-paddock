// Fails when a React effect callback can return a value (REVIEW #1). React calls whatever an effect
// returns as its cleanup on the next run or unmount; `useEffect(() => fn())` returns fn's result,
// which crashes navigation as soon as fn (say, a wrapped window.scrollTo) returns a non-function.
// Rule: effect callbacks are block-bodied, and `return` inside them returns nothing or a function.
import { readFileSync, readdirSync, statSync } from 'node:fs'
import { join } from 'node:path'

const files = []
const walk = (d) => {
  for (const f of readdirSync(d)) {
    const p = join(d, f)
    if (statSync(p).isDirectory()) walk(p)
    else if (/\.(t|j)sx?$/.test(f)) files.push(p)
  }
}
walk(new URL('../src', import.meta.url).pathname)

const bad = []
for (const f of files) {
  const src = readFileSync(f, 'utf8')
  // expression-bodied arrow passed to an effect hook: useEffect(() => expr, ...) / useEffect(async () => ...)
  const re = /use(?:Layout|Insertion)?Effect\(\s*(async\s*)?\([^)]*\)\s*=>(?!\s*\{)/g
  for (const m of src.matchAll(re)) bad.push(`${f}:${src.slice(0, m.index).split('\n').length}: effect callback must be block-bodied`)
  for (const m of src.matchAll(/use(?:Layout|Insertion)?Effect\(\s*async\b/g)) bad.push(`${f}:${src.slice(0, m.index).split('\n').length}: async effect returns a Promise`)
}
if (bad.length) {
  console.error(bad.join('\n'))
  process.exit(1)
}
console.log(`check-effects: ${files.length} files ok`)
