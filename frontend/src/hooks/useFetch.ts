import { useEffect, useState } from 'react'
import { ApiError } from '../api/client'

export interface Fetched<T> { data: T | null; loading: boolean; error: ApiError | Error | null }

/** Runs `fn` whenever `deps` change; aborts the previous request. `enabled=false` clears the state. */
export function useFetch<T>(fn: (signal: AbortSignal) => Promise<T>, deps: unknown[], enabled = true): Fetched<T> {
  const [state, setState] = useState<Fetched<T>>({ data: null, loading: enabled, error: null })
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)
  return state
}
