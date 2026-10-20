import React from 'react';
import { AlertTriangle, Ban, Check, Clock3, Phone, Pill, ShieldAlert, Utensils } from 'lucide-react';

const KICKERS = {
  en: { dose: 'Step 1 · Dose', freq: 'Step 2 · Schedule', time: 'Step 3 · Food & time', avoid: 'Be careful', warn: 'Urgent', emergency: 'Emergency? Call 112 or go to the nearest hospital.' },
  hi: { dose: 'चरण 1 · खुराक', freq: 'चरण 2 · समय', time: 'चरण 3 · खाना और समय', avoid: 'सावधान रहें', warn: 'ज़रूरी', emergency: 'आपातकाल में 112 पर कॉल करें या नज़दीकी अस्पताल जाएं।' },
  mr: { dose: 'पायरी 1 · डोस', freq: 'पायरी 2 · वेळ', time: 'पायरी 3 · जेवण आणि वेळ', avoid: 'काळजी घ्या', warn: 'तातडीचे', emergency: 'आणीबाणीत 112 वर कॉल करा किंवा जवळच्या रुग्णालयात जा.' },
};

function Card({ variant, icon: Icon, kicker, card, itemIcon: ItemIcon = Check, children }) {
  if (!card) return null;
  return (
    <article className={`card card-${variant}`}>
      <div className="card-head">
        <span className="card-icon"><Icon /></span>
        <div>
          <span className="card-kicker">{kicker}</span>
          <h3>{card.title}</h3>
        </div>
      </div>
      {card.badge && <span className="card-badge">{card.badge}</span>}
      {card.content && <p className="card-content">{card.content}</p>}
      {card.items?.length > 0 && (
        <ul className="card-list">
          {card.items.map((item, i) => (
            <li key={i}><ItemIcon />{item}</li>
          ))}
        </ul>
      )}
      {children}
    </article>
  );
}

export default function StructuredCards({ cards, language }) {
  if (!cards) return null;
  const k = KICKERS[language] || KICKERS.en;

  return (
    <div lang={language} style={{ display: 'grid', gap: '1rem' }}>
      <div className="cards">
        <Card variant="dose" icon={Pill} kicker={k.dose} card={cards.dosage} />
        <Card variant="freq" icon={Clock3} kicker={k.freq} card={cards.frequency} />
        <Card variant="time" icon={Utensils} kicker={k.time} card={cards.timing} />
      </div>
      <div className="cards cards-wide">
        <Card variant="avoid" icon={ShieldAlert} kicker={k.avoid} card={cards.precautions} itemIcon={Ban} />
        <Card variant="warn" icon={AlertTriangle} kicker={k.warn} card={cards.warning_signs} itemIcon={AlertTriangle}>
          <p className="emergency-line"><Phone /> {k.emergency}</p>
        </Card>
      </div>
    </div>
  );
}
