import { Navigate, Route, Routes } from 'react-router-dom'
import { AppShell } from './components/Layout'
import Landing from './pages/Landing'
import Home from './pages/Home'
import Briefcase from './pages/Briefcase'
import SurveyPage from './pages/Survey'
import JourneyLayout from './pages/journey/JourneyLayout'
import OutsideInSetup from './pages/journey/OutsideInSetup'
import StageSummary from './pages/journey/StageSummary'
import InsideOutInput from './pages/journey/InsideOutInput'
import StageRunPage from './pages/journey/StageRunPage'
import FinalReadout from './pages/journey/FinalReadout'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      {/* public page for invited directors: no sign-in, never shows the assessment */}
      <Route path="/survey/:token" element={<SurveyPage />} />
      <Route element={<AppShell />}>
        <Route path="/home" element={<Home />} />
        <Route path="/briefcase" element={<Briefcase />} />
        <Route path="/journey" element={<JourneyLayout />}>
          <Route path="setup" element={<OutsideInSetup />} />
          <Route path="outside-in" element={<StageSummary stage="oi" />} />
          <Route path="inside-out" element={<InsideOutInput />} />
          <Route path="inside-out/run" element={<StageRunPage />} />
          <Route path="inside-out/readout" element={<StageSummary stage="io" />} />
          <Route path="actions" element={<FinalReadout />} />
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
