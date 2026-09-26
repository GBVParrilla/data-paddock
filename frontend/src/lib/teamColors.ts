/** Team identity colors (approximate liveries), used to highlight a selected driver's line/border. */
export const TEAM_COLORS: Record<string, string> = {
  Mercedes: '#00D7B6',
  Ferrari: '#ED1131',
  'Red Bull Racing': '#3671C6',
  McLaren: '#FF8000',
  'Aston Martin': '#229971',
  Alpine: '#0093CC',
  Williams: '#64C4FF',
  'Racing Bulls': '#6692FF',
  Audi: '#A6053B',
  'Haas F1 Team': '#B6BABD',
  Cadillac: '#C9A227',
}
const FALLBACK = ['#3987e5', '#eb6834', '#1baf7a', '#eda100']

export function teamColor(team: string | null | undefined): string {
  if (team && TEAM_COLORS[team]) return TEAM_COLORS[team]
  if (!team) return FALLBACK[0]
  // stable hash fallback for an unmapped team name
  let h = 0
  for (let i = 0; i < team.length; i++) h = (h * 31 + team.charCodeAt(i)) >>> 0
  return FALLBACK[h % FALLBACK.length]
}

function mix(hex: string, withHex: string, amount: number): string {
  const a = parseInt(hex.slice(1), 16)
  const b = parseInt(withHex.slice(1), 16)
  const ar = (a >> 16) & 255, ag = (a >> 8) & 255, ab = a & 255
  const br = (b >> 16) & 255, bg = (b >> 8) & 255, bb = b & 255
  const r = Math.round(ar + (br - ar) * amount)
  const g = Math.round(ag + (bg - ag) * amount)
  const bl = Math.round(ab + (bb - ab) * amount)
  return `#${[r, g, bl].map((v) => v.toString(16).padStart(2, '0')).join('')}`
}

/** Colors for up to two selected drivers. Teammates (same team) get the same base hue,
 * so the second slot is lightened to stay distinguishable. */
export function slotColors(teams: (string | null | undefined)[]): string[] {
  const base = teams.map((t) => teamColor(t))
  if (base.length === 2 && base[0] === base[1]) {
    return [base[0], mix(base[1], '#ffffff', 0.45)]
  }
  return base
}
