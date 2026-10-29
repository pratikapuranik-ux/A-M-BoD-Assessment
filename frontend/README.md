# Board Assessment web app (React 18 + TypeScript)

Day 1 / Day 2 board assessment front end. The browser grades nothing: the FastAPI backend returns the graded "view"
model and this app renders it. The HTTP contract is the same as the legacy `server/app.py`.

## Run

    npm install
    npm run dev        # http://127.0.0.1:5174, proxies /api to http://127.0.0.1:8000
    npm run typecheck
    npm run build

On Windows paths containing `&`, the `.bin` shims fail; call the tools through node instead, for example
`node node_modules/typescript/bin/tsc --noEmit` and `node node_modules/vite/bin/vite.js build`.

## Layout

- `src/api` `client.ts` (fetch, errors, 409 job attach), `queries.ts` (TanStack Query hook per endpoint, job polling every 1.5 s), `types.ts`, `viewTypes.ts` (report View model).
- `src/store` `session.ts` (sign-in, selected company, stage flags; persisted per tab), `insideOut.ts` (draft files, add-company form, runs in flight), `reportUi.ts` (report UI state).
- `src/pages` Landing, Home, Briefcase, `journey/*` (setup, outside-in readout, inside-out input, live run, inside-out readout, final five actions), Survey (public `/survey/:token`).
- `src/report` the report/dashboard renderer (`ReportView`).
- `src/components` Layout, ui (buttons, Radix Dialog/Tabs/Tooltip/Accordion wrappers, toasts), JobRunner (follows background jobs after the page is left).
- `src/styles/legacy.css` the brand stylesheet ported from `css/styles.css`; `tailwind.config.cjs` carries the A&M palette.

## Routes

`/` landing and sign-in (`/?take=<token>` forwards to `/survey/<token>`), `/home`, `/briefcase`,
`/journey/setup`, `/journey/outside-in`, `/journey/inside-out`, `/journey/inside-out/run`, `/journey/inside-out/readout`, `/journey/actions`.
