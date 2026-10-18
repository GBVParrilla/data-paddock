import { useEffect } from 'react'

const SITE = 'Data Paddock'

/** Per-route document title (shared links and browser tabs say what the page is). */
export function useTitle(title: string | null | undefined) {
  useEffect(() => {
    document.title = title ? `${title} · ${SITE}` : SITE
  }, [title])
}
