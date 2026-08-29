import { lazy, Suspense } from 'react'

const App = lazy(() => import('./App.tsx'))
const LandingPage = lazy(() => import('./landing/LandingPage.tsx'))

const isConsole = window.location.pathname === '/app' || window.location.pathname.startsWith('/app/')

export default function Root() {
  return <Suspense fallback={null}>{isConsole ? <App /> : <LandingPage />}</Suspense>
}
