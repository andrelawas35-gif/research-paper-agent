import { Routes, Route, Link, useLocation } from 'react-router-dom';
import RegulationFlow from './pages/RegulationFlow';
import PrivacyCenter from './pages/PrivacyCenter';
import { useState, useEffect } from 'react';

function App() {
  const location = useLocation();
  const [offline, setOffline] = useState(!navigator.onLine);

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

  const isRegulation = location.pathname.startsWith('/regulation');

  return (
    <div className="min-h-screen flex flex-col safe-top">
      {/* Offline banner */}
      {offline && (
        <div className="bg-amber-600 text-amber-50 text-center text-sm py-2 px-4">
          You are offline. The deterministic Regulation protocol and safety
          resources remain available.
        </div>
      )}

      {/* Navigation */}
      {!isRegulation && (
        <nav className="bg-slate-900 border-b border-slate-800 px-4 py-3">
          <div className="max-w-lg mx-auto flex items-center justify-between">
            <Link to="/" className="text-lg font-semibold text-indigo-400">
              PKM
            </Link>
            <div className="flex gap-4 text-sm">
              <Link
                to="/regulation"
                className="text-slate-400 hover:text-slate-200 transition-colors"
              >
                Regulation
              </Link>
              <Link
                to="/privacy"
                className="text-slate-400 hover:text-slate-200 transition-colors"
              >
                Privacy
              </Link>
            </div>
          </div>
        </nav>
      )}

      {/* Main content */}
      <main className="flex-1">
        <Routes>
          <Route path="/regulation/*" element={<RegulationFlow />} />
          <Route path="/privacy" element={<PrivacyCenter />} />
          <Route
            path="/"
            element={
              <div className="max-w-lg mx-auto px-4 py-12 text-center">
                <h1 className="text-2xl font-bold mb-4">
                  Personal Knowledge Manager
                </h1>
                <p className="text-slate-400 mb-8">
                  Your private space for thinking, learning, and growing.
                </p>
                <div className="flex flex-col gap-4 max-w-xs mx-auto">
                  <Link to="/regulation" className="btn-primary text-center">
                    Start Regulation Check-In
                  </Link>
                  <Link to="/privacy" className="btn-secondary text-center">
                    Data & Privacy Center
                  </Link>
                </div>
              </div>
            }
          />
        </Routes>
      </main>
    </div>
  );
}

export default App;
