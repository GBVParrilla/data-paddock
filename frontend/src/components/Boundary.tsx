import { Component, type ErrorInfo, type ReactNode } from 'react'
import { Link } from 'react-router-dom'

type Props = { label: string; children: ReactNode; page?: boolean }
type State = { error: Error | null; attempt: number }

/** Contains a crash to one panel (or, with `page`, the whole route) and offers a retry. */
export class Boundary extends Component<Props, State> {
  state: State = { error: null, attempt: 0 }

  static getDerivedStateFromError(error: Error): Partial<State> {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.warn(`[${this.props.label}] failed to render`, error, info.componentStack)
  }

  render() {
    if (!this.state.error) return <div key={this.state.attempt} className="contents">{this.props.children}</div>
    const retry = () => this.setState((s) => ({ error: null, attempt: s.attempt + 1 }))
    if (this.props.page) {
      return (
        <div className="wrap pt-16 pb-24 text-center">
          <h1 className="h1">Something went wrong on this page</h1>
          <p className="t2 mt-3">The rest of the site is fine. Try again, or head back to the races.</p>
          <div className="mt-6 flex justify-center gap-3">
            <button className="btn" onClick={retry}>Try again</button>
            <Link className="btn-ghost" to="/" onClick={retry}>All races</Link>
          </div>
        </div>
      )
    }
    return (
      <section className="panel p-5 flex flex-wrap items-center justify-between gap-3" role="alert">
        <div>
          <div className="h2">{this.props.label} couldn't be shown</div>
          <p className="t2 text-[13px] mt-1">Something in this section failed to load. Everything else on the page still works.</p>
        </div>
        <button className="btn" onClick={retry}>Reload this section</button>
      </section>
    )
  }
}

export function NotFound({ what = 'page' }: { what?: string }) {
  return (
    <div className="wrap pt-16 pb-24 text-center">
      <div className="kicker">404</div>
      <h1 className="h1 mt-2">That {what} was not found</h1>
      <p className="t2 mt-3">It may not have run yet, or the link is wrong.</p>
      <div className="mt-6 flex justify-center gap-3">
        <Link className="btn" to="/">All races</Link>
      </div>
    </div>
  )
}
