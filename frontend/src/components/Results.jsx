import React from 'react';
import { Copy, Cpu, Printer, RotateCcw, ShieldAlert, ShieldCheck, ShieldX } from 'lucide-react';
import AudioPlayer from './AudioPlayer';
import StructuredCards from './StructuredCards';
import Checklist from './Checklist';
import Timetable from './Timetable';
import Glossary from './Glossary';
import VerificationCard from './VerificationCard';

const HEADINGS = {
  en: 'Your medicine guide',
  hi: 'आपकी दवा की जानकारी',
  mr: 'तुमच्या औषधाची माहिती',
};

const STATUS = {
  VERIFIED: { cls: 'pill-ok', icon: ShieldCheck, label: 'All key facts verified' },
  CAUTION: { cls: 'pill-warn', icon: ShieldAlert, label: 'Review flagged items' },
  CRITICAL_MISMATCH: { cls: 'pill-bad', icon: ShieldX, label: 'Check with your pharmacist' },
};

function buildPlainText(result) {
  const c = result.structured_cards;
  const section = (card) => [
    `${card.title}${card.badge ? ` (${card.badge})` : ''}`,
    card.content,
    ...(card.items || []).map((i) => `  - ${i}`),
  ].join('\n');
  return [
    'HealthBridge AI · Medicine guide',
    '',
    result.simplified_text,
    '',
    ...[c.dosage, c.frequency, c.timing, c.precautions, c.warning_signs].map((card) => `${section(card)}\n`),
    c.patient_summary?.length ? `Checklist:\n${c.patient_summary.map((p) => `  [ ] ${p}`).join('\n')}\n` : '',
    `Safety score: ${result.verification.score}/100`,
    '',
    'This is not medical advice. Always follow your doctor and pharmacist.',
  ].join('\n');
}

export default function Results({ result, originalText, onStartOver, onToast }) {
  const lang = result.target_language;
  const status = STATUS[result.verification.status] || STATUS.CAUTION;
  const StatusIcon = status.icon;

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(buildPlainText(result));
      onToast('Instructions copied');
    } catch {
      onToast('Copy is blocked in this browser');
    }
  };

  return (
    <section className="results" aria-labelledby="results-title">
      <div className="print-only">
        <strong>HealthBridge AI · Medicine guide</strong> · {new Date().toLocaleDateString()}
      </div>

      <div className="results-head">
        <div>
          <span className="section-label">Result</span>
          <h2 id="results-title" lang={lang}>{HEADINGS[lang] || HEADINGS.en}</h2>
          <div className="results-meta">
            <span className={`pill ${status.cls}`}><StatusIcon /> {status.label} · {result.verification.score}/100</span>
            <span className="pill pill-neutral">{result.target_language_name}</span>
          </div>
        </div>
        <div className="results-actions no-print">
          <button type="button" className="btn btn-secondary btn-sm" onClick={copy}><Copy /> Copy</button>
          <button type="button" className="btn btn-secondary btn-sm" onClick={() => window.print()}><Printer /> Print</button>
          <button type="button" className="btn btn-ghost btn-sm" onClick={onStartOver}><RotateCcw /> New</button>
        </div>
      </div>

      <div className="panel summary-panel">
        <p className="summary-text" lang={lang}>{result.simplified_text}</p>
        <AudioPlayer
          text={result.structured_cards?.read_aloud_text || result.simplified_text}
          language={lang}
        />
      </div>

      <StructuredCards cards={result.structured_cards} language={lang} />

      <Timetable entries={result.timetable} language={lang} onToast={onToast} />

      <Glossary terms={result.glossary} language={lang} />

      {result.structured_cards?.patient_summary?.length > 0 && (
        <Checklist items={result.structured_cards.patient_summary} language={lang} />
      )}

      <VerificationCard
        verification={result.verification}
        extracted={result.extracted_from_original}
        originalText={originalText}
        simplifiedText={result.simplified_text}
        language={lang}
      />

      <p className="engine-line">
        <Cpu /> Written by {result.ai_provider} · {result.ai_model}
      </p>
      <p className="engine-line" style={{ marginTop: '-.75rem' }}>
        Not medical advice. Always confirm with your doctor or pharmacist.
      </p>
    </section>
  );
}
