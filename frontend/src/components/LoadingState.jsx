import React, { useEffect, useState } from 'react';
import { CheckCircle2, Circle, LoaderCircle } from 'lucide-react';

const STEPS = [
  'Reading doses, timings and warnings',
  'Writing simple instructions',
  'Checking every number against the original',
];

export default function LoadingState() {
  const [step, setStep] = useState(0);
  const [slow, setSlow] = useState(false);

  useEffect(() => {
    const timer = setInterval(() => setStep((s) => Math.min(s + 1, STEPS.length - 1)), 900);
    const slowTimer = setTimeout(() => setSlow(true), 6000);
    return () => { clearInterval(timer); clearTimeout(slowTimer); };
  }, []);

  return (
    <section className="results" aria-live="polite" aria-busy="true">
      <div className="panel panel-pad">
        <div className="skeleton" style={{ height: 28, width: '45%' }} />
        <div className="skeleton" style={{ height: 16, width: '90%', marginTop: 16 }} />
        <div className="skeleton" style={{ height: 16, width: '75%', marginTop: 10 }} />
        <ul className="loading-steps">
          {STEPS.map((label, i) => (
            <li key={label} className={i < step ? 'done' : i === step ? 'active' : ''}>
              {i < step ? <CheckCircle2 /> : i === step ? <LoaderCircle className="spin" /> : <Circle />}
              {label}
            </li>
          ))}
        </ul>
        {slow && (
          <p className="loading-hint">
            The AI is still writing. This usually takes under a minute, so please keep this page open.
          </p>
        )}
      </div>
      <div className="cards">
        {[0, 1, 2].map((i) => (
          <div key={i} className="card">
            <div className="skeleton" style={{ height: 40, width: 40, borderRadius: 12 }} />
            <div className="skeleton" style={{ height: 18, width: '60%' }} />
            <div className="skeleton" style={{ height: 14, width: '90%' }} />
          </div>
        ))}
      </div>
    </section>
  );
}
