import { useEffect, useState } from 'react'
import { ApiError } from '../api/client'

export interface Fetched<T> { data: T | null; loading: boolean; error: ApiError | Error | null }

/** Runs `fn` whenever `deps` change; aborts the previous request. `enabled=false` clears the state. */
export function useFetch<T>(fn: (signal: AbortSignal) => Promise<T>, deps: unknown[], enabled = true): Fetched<T> {
  const [state, setState] = useState<Fetched<T>>({ data: null, loading: enabled, error: null })
  // deps are plain values (ids, flags), so one string key tracks them all
  const key = JSON.stringify([enabled, ...deps])
  useEffect(() => {
    if (!enabled) {
      setState({ data: null, loading: false, error: null })
      return
    }
    const ctrl = new AbortController()
    setState((s) => ({ ...s, loading: true, error: null }))
    fn(ctrl.signal)
      .then((data) => setState({ data, loading: false, error: null }))
      .catch((err) => {
        if (err?.name === 'AbortError') return
        setState({ data: null, loading: false, error: err })
      })
    return () => ctrl.abort()
    // `fn` is a new closure each render; `key` says when its inputs changed
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key])
  return state
}
