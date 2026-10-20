import React from 'react';
import { BookOpen } from 'lucide-react';

const TEXT = {
  en: { title: 'Prescription terms explained', sub: 'What the abbreviations on your prescription mean.' },
  hi: { title: 'पर्चे के शब्दों का मतलब', sub: 'आपके पर्चे पर लिखे छोटे शब्दों का अर्थ।' },
  mr: { title: 'प्रिस्क्रिप्शनमधील शब्दांचा अर्थ', sub: 'तुमच्या प्रिस्क्रिप्शनवरील संक्षेपांचा अर्थ.' },
};

export default function Glossary({ terms, language }) {
  if (!terms?.length) return null;
  const t = TEXT[language] || TEXT.en;

  return (
    <section className="panel panel-pad" lang={language} aria-labelledby="glossary-title">
      <div className="panel-head" style={{ marginBottom: '1rem' }}>
        <div className="panel-title">
          <span className="panel-icon"><BookOpen /></span>
          <div>
            <h2 id="glossary-title">{t.title}</h2>
            <p className="panel-sub">{t.sub}</p>
          </div>
        </div>
      </div>
      <dl className="glossary">
        {terms.map((g) => (
          <div key={g.term} className="glossary-item">
            <dt><code>{g.found_as}</code></dt>
            <dd>{g.meaning}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}
