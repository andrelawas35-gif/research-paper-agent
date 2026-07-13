import { Routes, Route, useLocation } from 'react-router-dom';
import RegulationFlow from './pages/RegulationFlow';
import PrivacyCenter from './pages/PrivacyCenter';
import { NowScreen } from './pages/NowScreen';
import { FocusedFlowNav } from './components/Navigation';
import { StatusNotice } from './components/StatusNotice';
import { useState, useEffect } from 'react';
import { UnlockScreen } from './pages/UnlockScreen';
import * as api from './api/client';

function App() {
  const location = useLocation();
  const [offline, setOffline] = useState(!navigator.onLine);
  const [degraded, setDegraded] = useState(false);
  const [authState, setAuthState] = useState<'checking' | 'locked' | 'unlocked'>(
    api.isAuthenticated() ? 'checking' : 'locked',
  );

  useEffect(() => {
    if (authState !== 'checking') return;
    void api.me()
      .then(() => setAuthState('unlocked'))
      .catch(() => {
        api.clearApiKey();
        setAuthState('locked');
      });
  }, [authState]);

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
      .then(async r => {
        const body = await r.json().catch(() => ({}));
        if (!r.ok || body.status !== 'ready') setDegraded(true);
      })
      .catch(() => setDegraded(true));
  }, []);

  const isRegulation = location.pathname.startsWith('/regulation');
  const mayUsePublicOfflineProtocol = offline && isRegulation;

  if (authState === 'checking' && !mayUsePublicOfflineProtocol) {
    return <div className="min-h-screen bg-paper" aria-label="Checking access" />;
  }

  if (authState === 'locked' && !mayUsePublicOfflineProtocol) {
    return <UnlockScreen onUnlock={() => setAuthState('unlocked')} />;
  }

  return (
    <div className="min-h-screen flex flex-col bg-paper safe-top">
      {offline && (
        <StatusNotice variant="caution">
          You are offline. The deterministic Regulation protocol and safety resources remain available.
        </StatusNotice>
      )}
      {degraded && !offline && (
        <StatusNotice variant="capability">
          Some local services are unavailable. Regulation may be limited.
        </StatusNotice>
      )}

      {isRegulation && (
        <FocusedFlowNav onBack={() => window.history.back()} title="Regulation" />
      )}

      <main className="flex-1">
        <Routes>
          <Route path="/" element={<NowScreen />} />
          <Route path="/regulation" element={<RegulationFlow />} />
          <Route path="/privacy" element={<PrivacyCenter />} />
        </Routes>
      </main>
    </div>
  );
}

export default App;
