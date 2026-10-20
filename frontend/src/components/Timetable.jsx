import React, { useState } from 'react';
import { CalendarClock, CalendarPlus, Check, CloudSun, Moon, Sun, Sunset, Utensils } from 'lucide-react';
import { buildCalendar, downloadFile } from '../utils/calendar';
import { load, save } from '../utils/storage';

const SLOTS = [
  { key: 'morning', icon: Sun },
  { key: 'afternoon', icon: CloudSun },
  { key: 'evening', icon: Sunset },
  { key: 'night', icon: Moon },
];

const DEFAULT_TIMES = { morning: '08:00', afternoon: '14:00', evening: '18:00', night: '21:00' };

const TEXT = {
  en: {
    title: 'Your daily medicine timetable',
    sub: 'When to take each medicine. Change the times to fit your day, then add reminders to your phone.',
    slots: { morning: 'Morning', afternoon: 'Afternoon', evening: 'Evening', night: 'Night' },
    medicine: 'Medicine', asNeeded: 'Only when needed', alsoAsNeeded: 'only if needed', weekly: 'once a week only',
    days: (n) => `for ${n} days`, ongoing: 'until your doctor says to stop',
    add: 'Add reminders to calendar', note: 'Works with Google Calendar, Apple Calendar and Outlook. Open the downloaded file to import it.',
    take: 'Take', food: 'How', noDuration: 'Repeats for 30 days. Ask your doctor how long to continue.',
    disclaimer: 'Reminder created by HealthBridge AI. Always follow your doctor\'s instructions.',
    saved: (n) => `${n} reminders downloaded`,
  },
  hi: {
    title: 'आपकी रोज़ की दवा की समय-सारणी',
    sub: 'कौन-सी दवा कब लेनी है। समय अपने दिन के हिसाब से बदलें, फिर फ़ोन में रिमाइंडर जोड़ें।',
    slots: { morning: 'सुबह', afternoon: 'दोपहर', evening: 'शाम', night: 'रात' },
    medicine: 'दवा', asNeeded: 'सिर्फ़ ज़रूरत पड़ने पर', alsoAsNeeded: 'ज़रूरत हो तभी', weekly: 'सिर्फ़ हफ़्ते में एक बार',
    days: (n) => `${n} दिन तक`, ongoing: 'जब तक डॉक्टर बंद करने को न कहें',
    add: 'कैलेंडर में रिमाइंडर जोड़ें', note: 'Google Calendar, Apple Calendar और Outlook में काम करता है। डाउनलोड की गई फ़ाइल खोलें।',
    take: 'दवा लें', food: 'कैसे', noDuration: '30 दिन तक दोहराया जाएगा। डॉक्टर से पूछें कि कब तक लेनी है।',
    disclaimer: 'HealthBridge AI द्वारा बनाया गया रिमाइंडर। हमेशा डॉक्टर की सलाह मानें।',
    saved: (n) => `${n} रिमाइंडर डाउनलोड हुए`,
  },
  mr: {
    title: 'तुमचे रोजचे औषध वेळापत्रक',
    sub: 'कोणते औषध कधी घ्यायचे. वेळा तुमच्या दिनक्रमानुसार बदला आणि फोनमध्ये रिमाइंडर जोडा.',
    slots: { morning: 'सकाळ', afternoon: 'दुपार', evening: 'संध्याकाळ', night: 'रात्र' },
    medicine: 'औषध', asNeeded: 'फक्त गरज असेल तेव्हा', alsoAsNeeded: 'गरज असेल तरच', weekly: 'फक्त आठवड्यातून एकदा',
    days: (n) => `${n} दिवस`, ongoing: 'डॉक्टर थांबवायला सांगेपर्यंत',
    add: 'कॅलेंडरमध्ये रिमाइंडर जोडा', note: 'Google Calendar, Apple Calendar आणि Outlook मध्ये चालते. डाउनलोड केलेली फाइल उघडा.',
    take: 'औषध घ्या', food: 'कसे', noDuration: '30 दिवस पुनरावृत्ती होईल. किती दिवस घ्यायचे ते डॉक्टरांना विचारा.',
    disclaimer: 'HealthBridge AI ने तयार केलेला रिमाइंडर. नेहमी डॉक्टरांच्या सूचना पाळा.',
    saved: (n) => `${n} रिमाइंडर डाउनलोड झाले`,
  },
};

export default function Timetable({ entries, language, onToast }) {
  const t = TEXT[language] || TEXT.en;
  const [times, setTimes] = useState(() => ({ ...DEFAULT_TIMES, ...load('hb-slot-times', {}) }));

  if (!entries?.length) return null;
  const used = SLOTS.filter((s) => entries.some((e) => e.slots.includes(s.key)));
  const scheduled = entries.filter((e) => e.slots.length > 0);
  const asNeededOnly = entries.filter((e) => e.slots.length === 0 && e.as_needed);

  const setTime = (slot, value) => {
    const next = { ...times, [slot]: value };
    setTimes(next);
    save('hb-slot-times', next);
  };

  const addToCalendar = () => {
    const { ics, count } = buildCalendar(scheduled, times, t);
    downloadFile(ics, 'medicine-reminders.ics', 'text/calendar;charset=utf-8');
    onToast?.(t.saved(count));
  };

  return (
    <section className="panel panel-pad" lang={language} aria-labelledby="timetable-title">
      <div className="panel-head">
        <div className="panel-title">
          <span className="panel-icon"><CalendarClock /></span>
          <div>
            <h2 id="timetable-title">{t.title}</h2>
            <p className="panel-sub">{t.sub}</p>
          </div>
        </div>
      </div>

      {scheduled.length > 0 && (
        <div className="timetable-scroll">
          <table className="timetable">
            <thead>
              <tr>
                <th scope="col">{t.medicine}</th>
                {used.map(({ key, icon: Icon }) => (
                  <th scope="col" key={key} className="slot-head">
                    <span className="slot-name"><Icon /> {t.slots[key]}</span>
                    <input
                      type="time"
                      className="no-print"
                      value={times[key]}
                      onChange={(e) => setTime(key, e.target.value || DEFAULT_TIMES[key])}
                      aria-label={`${t.slots[key]} time`}
                    />
                    <span className="print-only">{times[key]}</span>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {scheduled.map((entry) => (
                <tr key={entry.medicine}>
                  <th scope="row">
                    <strong>{entry.medicine}</strong>
                    <span className="tt-meta">
                      {[entry.weekly && t.weekly, entry.amount, entry.duration_days ? t.days(entry.duration_days) : t.ongoing, entry.as_needed && t.alsoAsNeeded]
                        .filter(Boolean).join(' · ')}
                    </span>
                    {entry.food_note && <span className="tt-food"><Utensils /> {entry.food_note}</span>}
                  </th>
                  {used.map(({ key }) => (
                    <td key={key}>
                      {entry.slots.includes(key)
                        ? <span className="tt-dose" aria-label={`${t.slots[key]}: ${t.take}`}><Check strokeWidth={3} /></span>
                        : <span className="tt-none" aria-label="—">–</span>}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {asNeededOnly.length > 0 && (
        <ul className="tt-prn">
          {asNeededOnly.map((entry) => (
            <li key={entry.medicine}>
              <strong>{entry.medicine}</strong>
              {entry.amount && <> · {entry.amount}</>} · {t.asNeeded}
            </li>
          ))}
        </ul>
      )}

      {scheduled.length > 0 && (
        <div className="tt-actions no-print">
          <button type="button" className="btn btn-primary" onClick={addToCalendar}>
            <CalendarPlus /> {t.add}
          </button>
          <p className="panel-sub">{t.note}</p>
        </div>
      )}
    </section>
  );
}
