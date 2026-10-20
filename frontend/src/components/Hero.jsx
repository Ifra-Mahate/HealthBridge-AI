import React from 'react';
import { ArrowDown, ArrowRight, Clock3, ClipboardPaste, Languages, Pill, ShieldCheck, Utensils, Volume2 } from 'lucide-react';

export default function Hero() {
  return (
    <>
      <section className="hero" id="top">
        <div>
          <p className="eyebrow">Clear care instructions</p>
          <h1>
            Medicine instructions, <em>made simple.</em>
          </h1>
          <p className="hero-lead">
            Paste a prescription and get clear, step-by-step guidance in English, Hindi or Marathi.
            Every dose, number and warning is checked against the original.
          </p>
          <div className="hero-actions">
            <a className="btn btn-primary btn-lg" href="#prescription">
              Simplify a prescription <ArrowDown />
            </a>
          </div>
          <ul className="hero-points">
            <li><Languages /> English, हिन्दी, मराठी</li>
            <li><ShieldCheck /> Automatic safety check</li>
            <li><Volume2 /> Read aloud</li>
          </ul>
        </div>

        <div className="hero-demo" aria-hidden="true">
          <div className="demo-stack">
            <div className="demo-before">
              <b>DOCTOR WROTE</b>
              Rx: Amoxicillin 500 mg PO TID x 7 days c meals
            </div>
            <span className="demo-arrow"><ArrowDown /></span>
            <div className="demo-card">
              <div className="demo-card-head">
                <h3>Amoxicillin</h3>
                <span className="pill pill-ok"><ShieldCheck /> Verified</span>
              </div>
              <div className="demo-rows">
                <div className="demo-row">
                  <span style={{ background: 'var(--brand-soft)', color: 'var(--brand)' }}><Pill /></span>
                  <div><strong>500 mg</strong> each time</div>
                </div>
                <div className="demo-row">
                  <span style={{ background: 'var(--blue-soft)', color: 'var(--blue)' }}><Clock3 /></span>
                  <div><strong>3 times a day</strong> for 7 days</div>
                </div>
                <div className="demo-row">
                  <span style={{ background: 'var(--ochre-soft)', color: 'var(--ochre)' }}><Utensils /></span>
                  <div>Take <strong>with food</strong></div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <ol className="steps" aria-label="How it works">
        <li className="step">
          <span className="step-num">1</span>
          <div>
            <h3><ClipboardPaste size={15} style={{ display: 'inline', verticalAlign: '-2px', marginRight: 4 }} />Paste</h3>
            <p>Type or paste the prescription exactly as written.</p>
          </div>
        </li>
        <li className="step">
          <span className="step-num">2</span>
          <div>
            <h3><Languages size={15} style={{ display: 'inline', verticalAlign: '-2px', marginRight: 4 }} />Choose a language</h3>
            <p>Get simple instructions in English, Hindi or Marathi.</p>
          </div>
        </li>
        <li className="step">
          <span className="step-num">3</span>
          <div>
            <h3><ArrowRight size={15} style={{ display: 'inline', verticalAlign: '-2px', marginRight: 4 }} />Read, listen, print</h3>
            <p>Check the safety score, listen aloud, or print a handout.</p>
          </div>
        </li>
      </ol>
    </>
  );
}
