import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './bakeoff/bakeoff.css'
import { BakeOff } from './bakeoff/BakeOff'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BakeOff />
  </StrictMode>,
)
