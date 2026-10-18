import { useEffect, useRef, useState, type ReactNode } from 'react'

/** Renders children only once the placeholder is near the viewport, so heavy below-the-fold panels
 * (and the chart library they load) don't hold up the first paint. */
export function WhenVisible({ children, minHeight, margin = '300px' }: { children: ReactNode; minHeight: number; margin?: string }) {
  const ref = useRef<HTMLDivElement>(null)
  const [shown, setShown] = useState(typeof IntersectionObserver === 'undefined')
  useEffect(() => {
    if (shown || !ref.current) return
    const io = new IntersectionObserver((entries) => {
      if (entries.some((e) => e.isIntersecting)) {
        setShown(true)
        io.disconnect()
      }
    }, { rootMargin: margin })
    io.observe(ref.current)
    return () => io.disconnect()
  }, [shown, margin])
  return <div ref={ref} style={shown ? undefined : { minHeight }}>{shown ? children : <div className="skeleton" style={{ height: minHeight }} />}</div>
}
