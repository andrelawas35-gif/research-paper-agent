import { Routes, Route, useLocation } from 'react-router-dom';
import RegulationFlow from './pages/RegulationFlow';
import PrivacyCenter from './pages/PrivacyCenter';
import { NowScreen } from './pages/NowScreen';
import { FocusedFlowNav } from './components/Navigation';
import { StatusNotice } from './components/StatusNotice';
import { useState, useEffect, useCallback } from 'react';

function App() {
  const location = useLocation();
  const [offline, setOffline] = useState(!navigator.onLine);
  const [degraded, setDegraded] = useState(false);

  useEffect(() => {
    const goOnline = () => setOffline(false);
    const goOffline = () => setOffline(true);
    window.addEventListener('online', goOnline);
    window.addEventListener('offline', goOffline);
    return () => {
      window.removeEventListener('online', goOnline);
      window.removeEventListener('offline', goOffline);
    };
  }, []);

  useEffect(() => {
    fetch('/health/ready')
      .then(r => { if (!r.ok) setDegraded(true); })
      .catch(() => setDegraded(true));
  }, []);

  const isRegulation = location.pathname.startsWith('/regulation');

  return (
    <div className="min-h-screen flex flex-col bg-paper safe-top">
      {offline && (
        <StatusNotice variant="caution">
          You are offline. The deterministic Regulation protocol and safety resources remain available.
        </StatusNotice>
      )}
      {degraded && !offline && (
        <StatusNotice variant="capability">
          Model assistance is paused. Local protocol available.
        </StatusNotice>
      )}

      {isRegulation && (
        <FocusedFlowNav onBack={() => window.history.back()} title="Regulation" />
      )}

      <main className="flex-1">
        <Routes>
          <Route path="/" element={<NowScreen offline={offline} degraded={degraded} />} />
          <Route path="/regulation" element={<RegulationFlow />} />
          <Route path="/privacy" element={<PrivacyCenter />} />
        </Routes>
      </main>
    </div>
  );
}

export default App;
