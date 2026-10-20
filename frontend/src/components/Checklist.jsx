import React, { useState } from 'react';
import { Check, ListChecks } from 'lucide-react';

const TEXT = {
  en: { title: 'Daily checklist', sub: 'Tick each item as you do it today.', done: 'done' },
  hi: { title: 'रोज़ की चेकलिस्ट', sub: 'आज जो काम कर लिया, उस पर निशान लगाएं।', done: 'पूरे' },
  mr: { title: 'दैनंदिन यादी', sub: 'आज केलेल्या गोष्टींवर खूण करा.', done: 'पूर्ण' },
};

export default function Checklist({ items, language }) {
  const [checked, setChecked] = useState(() => items.map(() => false));
  const t = TEXT[language] || TEXT.en;
  const doneCount = checked.filter(Boolean).length;

  const toggle = (index) => setChecked((prev) => prev.map((v, i) => (i === index ? !v : v)));

  return (
    <section className="panel panel-pad" lang={language} aria-labelledby="checklist-title">
      <div className="panel-head" style={{ marginBottom: '1rem' }}>
        <div className="panel-title">
          <span className="panel-icon"><ListChecks /></span>
          <div>
            <h2 id="checklist-title">{t.title}</h2>
            <p className="panel-sub">{t.sub}</p>
          </div>
        </div>
        <span className="checklist-progress" aria-live="polite">{doneCount}/{items.length} {t.done}</span>
      </div>
      <ul className="checklist">
        {items.map((item, i) => (
          <li key={i} className="check-item">
            <input type="checkbox" id={`check-${i}`} checked={checked[i]} onChange={() => toggle(i)} />
            <label htmlFor={`check-${i}`}>
              <span className="check-box"><Check strokeWidth={3} /></span>
              <span className="check-text">{item}</span>
            </label>
          </li>
        ))}
      </ul>
    </section>
  );
}
