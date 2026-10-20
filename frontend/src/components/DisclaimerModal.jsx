import React, { useEffect, useRef } from 'react';
import { CheckCircle2, FlaskConical, Phone, Pill, ShieldAlert, Stethoscope } from 'lucide-react';

export default function DisclaimerModal({ isOpen, onClose }) {
  const buttonRef = useRef(null);

  useEffect(() => {
    if (!isOpen) return undefined;
    const previous = document.activeElement;
    buttonRef.current?.focus();
    const onKey = (e) => e.key === 'Escape' && onClose();
    document.addEventListener('keydown', onKey);
    document.body.style.overflow = 'hidden';
    return () => {
      document.removeEventListener('keydown', onKey);
      document.body.style.overflow = '';
      previous?.focus?.();
    };
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal" role="dialog" aria-modal="true" aria-labelledby="disclaimer-title" aria-describedby="disclaimer-desc">
        <div className="modal-head">
          <span className="panel-icon"><ShieldAlert /></span>
          <div>
            <h2 id="disclaimer-title">Before you start</h2>
            <p className="panel-sub">HealthBridge AI is an educational project, not a medical service.</p>
          </div>
        </div>

        <p id="disclaimer-desc" style={{ color: 'var(--text-2)' }}>
          This tool helps explain prescriptions in simpler words. It <strong>does not give medical advice</strong>,
          diagnose conditions, or replace your doctor.
        </p>

        <ul className="modal-list">
          <li><Stethoscope /><span><strong>Your doctor comes first.</strong> Never ignore or delay professional advice because of something shown here.</span></li>
          <li><Pill /><span><strong>Check with your pharmacist</strong> and your medicine label before starting, changing or stopping any medicine.</span></li>
          <li><FlaskConical /><span><strong>Example prescriptions are fictional</strong> and included only for demonstration.</span></li>
          <li><Phone /><span><strong>In an emergency</strong> such as a severe allergic reaction or overdose, call 112 (or 108 / 911) right away.</span></li>
        </ul>

        <div className="modal-foot">
          <button ref={buttonRef} type="button" className="btn btn-primary" onClick={onClose}>
            <CheckCircle2 /> I understand
          </button>
        </div>
      </div>
    </div>
  );
}
