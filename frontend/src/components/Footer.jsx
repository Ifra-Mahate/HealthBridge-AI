import React from 'react';
import { HeartPulse } from 'lucide-react';

export default function Footer({ onOpenDisclaimer }) {
  return (
    <footer className="site-footer">
      <div className="container">
        <div className="footer-grid">
          <div>
            <div className="brand" style={{ marginBottom: '.75rem' }}>
              <span className="brand-mark" style={{ width: '2rem', height: '2rem', borderRadius: 10 }}><HeartPulse size={16} /></span>
              <span className="brand-name">HealthBridge <span>AI</span></span>
            </div>
            <p>
              Helping patients understand their medicines. HealthBridge turns complex prescriptions into simple
              English, Hindi and Marathi, and checks that no dose, number or warning is lost along the way.
            </p>
          </div>
          <div>
            <h4>Built with</h4>
            <ul>
              <li>React, Vite and Tailwind</li>
              <li>Python and FastAPI</li>
              <li>Gemini, Groq or OpenAI (optional)</li>
              <li>Web Speech API for read-aloud</li>
            </ul>
          </div>
          <div>
            <h4>Safety</h4>
            <p>Every result passes a rule-based check of numbers, prohibitions, schedules and warning signs.</p>
            <button type="button" className="link-btn" style={{ marginTop: '.5rem' }} onClick={onOpenDisclaimer}>
              Read the medical disclaimer
            </button>
          </div>
        </div>
        <div className="footer-bottom">
          <span>© {new Date().getFullYear()} HealthBridge AI · Academic mini-project</span>
          <span>Not a substitute for professional medical advice.</span>
        </div>
      </div>
    </footer>
  );
}
