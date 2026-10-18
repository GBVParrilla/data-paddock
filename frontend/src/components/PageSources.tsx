import { usePageSources } from '../state/sources'

const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`

/** One line per page saying where its stories came from, worded from the stories actually shown. */
export function PageSources() {
  const c = usePageSources()
  if (!c.claude && !c.template && !c.edited) return null
  let text: string
  if (c.claude && c.template) text = `${plural(c.claude, 'story', 'stories')} on this page written by Claude from the timing data and fact-checked against it; ${c.template} computed from the data.`
  else if (c.claude) text = 'Stories on this page are written by Claude from the timing data and fact-checked against it.'
  else if (c.template) text = 'Stories on this page are computed from the timing data.'
  else text = ''
  if (c.edited) text = `${text} ${plural(c.edited, 'story was', 'stories were')} corrected by the editor.`.trim()
  return <p className="wrap mt-10 text-[12px] t3" data-page-sources>{text}</p>
}
