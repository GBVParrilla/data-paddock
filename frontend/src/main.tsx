import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'

// Links shared before path routing used "#/race/1": rewrite them to "/race/1" before the router starts.
if (window.location.hash.startsWith('#/')) {
  const base = import.meta.env.BASE_URL.replace(/\/$/, '')
  window.history.replaceState(null, '', `${base}${window.location.hash.slice(1)}`)
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
