import base from './base.json'

export const DRAFT = 'DRAFT ONLY - Requires review and approval by a qualified Alvarez and Marsal professional before use.'

export const DIMS = ['1', '2', '3', '4', '5', '6'] as const
export const DIMN: Record<string, string> = {
  '1': 'Customer Obsession', '2': 'Resisting Proxies', '3': 'Embracing External Trends',
  '4': 'High-Velocity Decision-Making', '5': 'Building over Protecting', '6': 'Liquidity and Capital Management',
}
export const DSHORT: Record<string, string> = { '1': 'Customer', '2': 'Proxies', '3': 'Trends', '4': 'Velocity', '5': 'Building', '6': 'Liquidity' }

/** The framework with no company loaded (js/data/base.js): what the landing page shows before sign-in. */
export const BASE = base as unknown as {
  ind: Record<string, string>
  read: string[]
  method: string[]
  scale: { min: number; grade: string; label: string }[]
  docs: [string, string][]
  q: [string, ...string[]][]
  modes: Record<string, string>
  anchors11: Record<string, string>
}
export const IDS = Object.keys(BASE.ind).sort((a, b) => a.localeCompare(b, undefined, { numeric: true }))

export const NUMW = ['no', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten', 'eleven', 'twelve', 'thirteen', 'fourteen', 'fifteen', 'sixteen', 'seventeen', 'eighteen', 'nineteen', 'twenty']
export const numWord = (n: number) => NUMW[n] ?? String(n)

export const MAX_OI_DOCS = 10
export const MAX_PEERS = 5
export const FILE_ACCEPT = '.pdf,.docx,.txt,.md'

