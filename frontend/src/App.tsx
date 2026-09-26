import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { Home } from './pages/Home'
import { SeasonArcPage } from './pages/SeasonArcPage'
import { TrackDetail } from './pages/TrackDetail'
import { StoreProvider } from './state/store'

export default function App() {
  return (
    <StoreProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/race/:eventId" element={<TrackDetail />} />
          <Route path="/season/:year" element={<SeasonArcPage />} />
        </Routes>
      </BrowserRouter>
    </StoreProvider>
  )
}
