// The Circuit atlas rules (REVIEW_ROUND3 #59, D6): the tells of a generated page stay out.
// Fails on: uppercase or tracked labels (`uppercase`, `tracking-*` classes, `text-transform: uppercase`);
// "→" in link or button text; meta strings joined with " · " in components and pages; a border radius
// over 3px anywhere but a data dot; and a near-black background in the stylesheet.
import { readFileSync, readdirSync, statSync } from 'node:fs'
import { join, relative } from 'node:path'

const root = new URL('../src', import.meta.url).pathname
const files = []
const walk = (d) => {
  for (const f of readdirSync(d)) {
    const p = join(d, f)
    if (statSync(p).isDirectory()) walk(p)
    else if (/\.(tsx?|css)$/.test(f)) files.push(p)
  }
}
walk(root)

const bad = []
const at = (f, src, i, why) => bad.push(`${relative(root, f)}:${src.slice(0, i).split('\n').length}: ${why}`)
for (const f of files) {
  const src = readFileSync(f, 'utf8')
  const rel = relative(root, f)
  if (f.endsWith('.css')) {
    for (const m of src.matchAll(/text-transform:\s*uppercase/g)) at(f, src, m.index, 'no all-caps labels')
    for (const m of src.matchAll(/letter-spacing:\s*0?\.0[3-9]em|letter-spacing:\s*0?\.[1-9]/g)) at(f, src, m.index, 'no tracked labels')
    // a radius over 3px, except a data dot (`.dot`)
    for (const m of src.matchAll(/^([^{}\n]*)\{[^}]*border-radius:\s*(\d+)px/gm)) if (Number(m[2]) > 3 && !/\.dot\b/.test(m[1])) at(f, src, m.index, `border-radius ${m[2]}px on ${m[1].trim()}`)
    for (const m of src.matchAll(/--(?:bg|paper)\s*:\s*#(0[0-9a-f]|1[0-4])[0-9a-f]{4}\b/gi)) at(f, src, m.index, 'no near-black background')
    continue
  }
  for (const m of src.matchAll(/className=(?:"|{`)[^"`]*\b(uppercase|tracking-[a-z0-9[\]-]+)/g)) at(f, src, m.index, `no ${m[1]} labels`)
  for (const m of src.matchAll(/→/g)) at(f, src, m.index, 'no → in link or button text')
  if (/^(components|pages)\//.test(rel)) {
    for (const m of src.matchAll(/join\('\s*·\s*'\)|[^\s{`'"(]\s·\s[^\s]|>\s*·\s*</g)) {
      const line = src.slice(src.lastIndexOf('\n', m.index) + 1, src.indexOf('\n', m.index))
      if (/useTitle\(|title=\{|title: `|^\s*(\/\/|\*|\/\*\*)/.test(line)) continue // document titles, tooltips and comments aren't page meta
      at(f, src, m.index, 'no meta strings joined with middle dots')
    }
  }
  for (const m of src.matchAll(/rounded-(sm|md|lg|xl|2xl|3xl|full|\[(\d+)px\])/g)) {
    if (m[2] && Number(m[2]) <= 3) continue
    at(f, src, m.index, `${m[0]}: radius is 0 on sections, 3px only on controls`)
  }
}
if (bad.length) {
  console.error(`check-design: ${bad.length} problem(s)\n` + bad.join('\n'))
  process.exit(1)
}
console.log(`check-design: ${files.length} files ok`)
