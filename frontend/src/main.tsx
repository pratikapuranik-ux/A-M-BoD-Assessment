import { installSnapshot } from './snapshot'  // first: it seeds the session before the app's store reads storage
import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, HashRouter } from 'react-router-dom'
import { QueryClientProvider } from '@tanstack/react-query'
import { queryClient } from './api/queries'
import App from './App'
import './index.css'
import './styles/legacy.css'

const SNAPSHOT = !!import.meta.env.VITE_SNAPSHOT  // a read-only copy opened from a file: no server, so no path-based routing
if (SNAPSHOT) installSnapshot()
const Router = SNAPSHOT ? HashRouter : BrowserRouter

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <Router>
        <App />
      </Router>
    </QueryClientProvider>
  </React.StrictMode>,
)
