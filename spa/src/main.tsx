import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
import { AppProvider } from './context'
import './styles.css'

// Tema: oscuro por defecto; el claro se activa a voluntad y se recuerda.
document.documentElement.setAttribute('data-theme', localStorage.getItem('aq_theme') || 'dark')

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter basename="/admin-portal">
      <AppProvider>
        <App />
      </AppProvider>
    </BrowserRouter>
  </React.StrictMode>,
)

if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => { navigator.serviceWorker.register('/admin-portal/sw.js', { scope: '/admin-portal/' }).catch(() => {}) })
}
