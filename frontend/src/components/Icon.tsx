import type { SVGProps } from 'react'

const IC = {
  home: '<path d="M3 10.5 12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z"/>',
  clip: '<rect x="5" y="4" width="14" height="17" rx="2"/><path d="M9 4h6v3H9zM9 12h6M9 16h4"/>',
  doc: '<path d="M7 3h7l5 5v13H7z"/><path d="M14 3v5h5"/>',
  check: '<path d="m5 12 5 5 9-10"/>',
  upload: '<path d="M12 16V4M7 9l5-5 5 5M4 20h16"/>',
  arrow: '<path d="M5 12h14M13 6l6 6-6 6"/>',
  dl: '<path d="M12 4v12M7 11l5 5 5-5M4 20h16"/>',
  brief: '<rect x="3" y="7" width="18" height="13" rx="2"/><path d="M9 7V5a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2M3 13h18"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  web: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c3 3 3 15 0 18M12 3c-3 3-3 15 0 18"/>',
  zip: '<rect x="5" y="3" width="14" height="18" rx="2"/><path d="M12 3v12M10 7h4M10 11h4"/>',
  dash: '<rect x="3" y="3" width="8" height="10" rx="1.5"/><rect x="13" y="3" width="8" height="6" rx="1.5"/><rect x="13" y="11" width="8" height="10" rx="1.5"/><rect x="3" y="15" width="8" height="6" rx="1.5"/>',
  mail: '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 7 9 6 9-6"/>',
  bld: '<path d="M4 21V5l8-2v18M12 8l8 2v11M8 8h.01M8 12h.01M8 16h.01M16 13h.01M16 17h.01M3 21h18"/>',
  lock: '<rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/>',
  trash: '<path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3"/>',
} as const

export type IconName = keyof typeof IC

export function Icon({ name, size = 18, ...rest }: { name: IconName; size?: number } & Omit<SVGProps<SVGSVGElement>, 'name'>) {
  return (
    <svg className="ic" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...rest} dangerouslySetInnerHTML={{ __html: IC[name] }} />
  )
}

/** A&M vertical logo (non-shadow version, per the brand guideline), drawn as vector so it stays crisp at any size. */
export function AmLogo({ white = false }: { white?: boolean }) {
  const ink = white ? '#FFFFFF' : '#002B49'
  return (
    <svg className="amlogo" viewBox="0 0 470 410" role="img" aria-label="Alvarez & Marsal">
      <path fill={ink} d="M5 405 230 5h63v400h-43V90L73 405z" />
      <path fill="#5E8AB4" d="M198 405V195l40-68v278zM305 127l40 68v210h-40z" />
      <g fill={ink} fontFamily="Arial,Helvetica,sans-serif" fontSize="84" textAnchor="middle">
        <text x="410" y="265">A</text><text x="410" y="335">&amp;</text><text x="410" y="405">M</text>
      </g>
    </svg>
  )
}
