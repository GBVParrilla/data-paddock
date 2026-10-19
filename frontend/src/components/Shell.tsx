import type { ReactNode } from 'react'
import { Link, NavLink, useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import { useFetch } from '../hooks/useFetch'
import { ModeSwitch } from '../state/mode'
import { useStore } from '../state/store'
import { PageSources } from './PageSources'

export function Brand() {
  return (
    <Link to="/" className="flex items-center gap-2 sm:gap-2.5" aria-label="Data Paddock home">
      <svg width="22" height="22" viewBox="0 0 32 32" aria-hidden="true"><rect x="6" y="5" width="8" height="22" rx="2" fill="var(--text)" /><rect x="17" y="5" width="9" height="9" rx="2" fill="var(--accent)" /></svg>
      <span className="font-semibold tracking-tight whitespace-nowrap text-[15px] hidden sm:inline">Data Paddock</span>
    </Link>
  )
}

export function Shell({ children }: { children: ReactNode }) {
  const { year, setYear } = useStore()
  const seasons = useFetch((s) => api.seasons(s), [])
  const nav = useNavigate()
  const link = ({ isActive }: { isActive: boolean }) => `text-[13px] font-medium ${isActive ? 'text-[var(--text)]' : 'text-[var(--text-2)] hover:text-[var(--text)]'}`
  return (
    <div className="min-h-screen flex flex-col">
      <header className="border-b" style={{ borderColor: 'var(--line)', background: 'var(--bg)' }}>
        <div className="wrap h-14 flex items-center gap-4 sm:gap-8">
          <Brand />
          <nav className="flex items-center gap-3.5 sm:gap-6" aria-label="Main">
            <NavLink to="/races" className={link}>Races</NavLink>
            <NavLink to={`/season/${year ?? ''}`} className={link}>Standings</NavLink>
          </nav>
          <div className="ml-auto"><ModeSwitch /></div>
          <div className={(seasons.data?.length ?? 0) <= 1 ? 'hidden' : ''}>
            <label className="sr-only" htmlFor="season">Season</label>
            <select
              id="season"
              className="btn pr-7 appearance-none"
              style={{ backgroundImage: 'linear-gradient(45deg, transparent 50%, var(--text-2) 50%), linear-gradient(135deg, var(--text-2) 50%, transparent 50%)', backgroundPosition: 'right 12px top 50%, right 8px top 50%', backgroundSize: '4px 4px', backgroundRepeat: 'no-repeat' }}
              value={year ?? ''}
              onChange={(e) => { setYear(Number(e.target.value)); nav('/') }}
            >
              {seasons.data?.map((s) => <option key={s.id} value={s.year}>{s.year}</option>)}
            </select>
          </div>
        </div>
      </header>
      {/* a full screen of room up front keeps the footer from jumping as data arrives (layout shift) */}
      <main className="flex-1 min-h-[calc(100vh-3.5rem)]">{children}<PageSources /></main>
      <footer className="border-t mt-16" style={{ borderColor: 'var(--line)' }}>
        <div className="wrap py-6 flex flex-wrap gap-x-6 gap-y-2 justify-between text-[12px] t3">
          <span>Timing data from OpenF1 and Jolpica. Circuit maps in F1's orientation via MultiViewer.</span>
          <span>Not affiliated with Formula 1.</span>
        </div>
      </footer>
    </div>
  )
}
