import { Link } from 'react-router-dom'
import { useTitle } from '../hooks/useTitle'
import { CHANGES } from '../lib/changelog'

const long = (iso: string) => new Date(`${iso}T12:00:00Z`).toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC' })

/** The public changelog: dated entries, newest first. */
export function ChangesPage() {
  useTitle('What changed')
  return (
    <div className="wrap pt-8 max-w-3xl">
      <h1 className="h-feature">What changed</h1>
      <p className="t2 mt-3 text-[15px]">New on Data Paddock, newest first.</p>
      {CHANGES.map((c) => (
        <section key={c.date} className="mt-8" aria-label={long(c.date)}>
          <h2 className="h2 !text-[17px]"><time dateTime={c.date}>{long(c.date)}</time></h2>
          <ul className="prose mt-2 space-y-1.5 list-disc pl-5">
            {c.items.map((it) => <li key={it}>{it}</li>)}
          </ul>
        </section>
      ))}
      <p className="t3 text-[13px] mt-10"><Link to="/" className="underline underline-offset-2 hover:text-[var(--text)]">Back to the season</Link></p>
    </div>
  )
}
