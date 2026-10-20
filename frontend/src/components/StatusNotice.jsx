import React, { useState } from 'react';
import { ExternalLink, KeyRound, RefreshCw, ServerOff } from 'lucide-react';

export default function StatusNotice({ backend, health, onRetry }) {
  const [showSetup, setShowSetup] = useState(false);

  if (backend === 'offline') {
    return (
      <div className="notice notice-bad top-notice" role="alert">
        <ServerOff />
        <div className="notice-body">
          <p><strong>The HealthBridge server isn't running.</strong> Start it in a terminal, then retry.</p>
          <pre>cd backend{'\n'}venv\Scripts\activate{'\n'}python run.py</pre>
        </div>
        <button type="button" className="btn btn-secondary btn-sm" onClick={onRetry}>
          <RefreshCw /> Retry
        </button>
      </div>
    );
  }

  if (backend === 'online' && health && !health.ai_configured) {
    return (
      <div className="notice notice-info top-notice">
        <KeyRound />
        <div className="notice-body">
          <p>
            <strong>Running on the built-in rule engine.</strong> Safety checks work fully. Add an AI key for more natural wording.{' '}
            <button type="button" className="link-btn" onClick={() => setShowSetup((v) => !v)} aria-expanded={showSetup}>
              {showSetup ? 'Hide setup' : 'How to set up AI'}
            </button>
          </p>
          {showSetup && (
            <>
              <p>
                Get a free key from Google AI Studio, add it as <code>GEMINI_API_KEY</code> in <code>backend/.env</code>, then restart the backend.{' '}
                <a href="https://aistudio.google.com/apikey" target="_blank" rel="noreferrer">
                  Open Google AI Studio <ExternalLink size={13} style={{ display: 'inline', verticalAlign: '-2px' }} />
                </a>
              </p>
              <pre>GEMINI_API_KEY=your_key_here</pre>
            </>
          )}
        </div>
      </div>
    );
  }

  return null;
}
