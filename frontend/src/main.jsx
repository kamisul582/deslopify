import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { Analytics } from '@vercel/analytics/react'
import './index.css'
import App from './App.jsx'
import SharedPage from './SharedPage.jsx'

const shared = window.location.pathname.match(/^\/r\/([A-Za-z0-9_-]{22})\/?$/)

createRoot(document.getElementById('root')).render(
  <StrictMode>
    {shared ? <SharedPage id={shared[1]} /> : <App />}
    <Analytics />
  </StrictMode>,
)
