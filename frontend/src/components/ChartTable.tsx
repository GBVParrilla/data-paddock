import { useId, type ReactNode } from 'react'

/**
 * The numbers behind a chart, closed by default: a table to read and a CSV to download (BENCHMARKS row 17,
 * TracingInsights and Our World in Data). `rows` are the table's cells; the CSV gets the same cells as text.
 */
export function ChartTable({ caption, head, rows, file }: { caption: string; head: string[]; rows: (string | number | null)[][]; file: string }) {
  const id = useId()
  const csv = [head, ...rows].map((r) => r.map((c) => (c === null ? '' : /[",\n]/.test(String(c)) ? `"${String(c).replace(/"/g, '""')}"` : String(c))).join(',')).join('\n')
  return (
    <details className="mt-2 text-[13px]" data-chart-table>
      <summary className="t2 cursor-pointer select-none py-1 hover:text-[var(--text)]" aria-controls={id}>The numbers</summary>
      <div id={id} className="mt-2">
        <div className="overflow-x-auto max-h-[420px] overflow-y-auto">
          <table className="tbl num">
            <caption className="sr-only">{caption}</caption>
            <thead><tr>{head.map((h, i) => <th key={i} scope="col" className={i ? 'text-right' : 'text-left'}>{h}</th>)}</tr></thead>
            <tbody>{rows.map((r, i) => <tr key={i}>{r.map((c, j) => <td key={j} className={j ? 'text-right' : ''}>{cell(c)}</td>)}</tr>)}</tbody>
          </table>
        </div>
        <a className="btn-ghost inline-block mt-2" download={file} href={`data:text/csv;charset=utf-8,${encodeURIComponent(csv)}`}>Download CSV</a>
      </div>
    </details>
  )
}

const cell = (c: string | number | null): ReactNode => (c === null || c === '' ? '–' : c)
