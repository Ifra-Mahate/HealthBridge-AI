// Builds an .ics calendar file with daily repeating medicine reminders.
// Times are "floating" (no time zone), so they ring at the same clock time wherever the phone is.

const pad = (n) => String(n).padStart(2, '0');
const escape = (text) => String(text).replace(/\\/g, '\\\\').replace(/;/g, '\\;').replace(/,/g, '\\,').replace(/\n/g, '\\n');
const DEFAULT_DAYS = 30;

const stamp = (date) =>
  `${date.getUTCFullYear()}${pad(date.getUTCMonth() + 1)}${pad(date.getUTCDate())}T${pad(date.getUTCHours())}${pad(date.getUTCMinutes())}00Z`;

/**
 * entries: timetable entries from the API
 * times: { morning: '08:00', ... }
 * labels: localised slot names
 */
export function buildCalendar(entries, times, labels) {
  const now = new Date();
  const start = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const lines = [
    'BEGIN:VCALENDAR',
    'VERSION:2.0',
    'PRODID:-//HealthBridge AI//Medicine Reminders//EN',
    'CALSCALE:GREGORIAN',
    'METHOD:PUBLISH',
  ];
  let count = 0;

  entries.forEach((entry, i) => {
    entry.slots.forEach((slot) => {
      const [h, m] = (times[slot] || '08:00').split(':').map(Number);
      const first = new Date(start);
      first.setHours(h, m, 0, 0);
      // If today's time has already passed, begin tomorrow
      if (first < now) first.setDate(first.getDate() + 1);
      const days = entry.duration_days || DEFAULT_DAYS;
      const occurrences = entry.weekly ? Math.max(1, Math.ceil(days / 7)) : days;
      const local = `${first.getFullYear()}${pad(first.getMonth() + 1)}${pad(first.getDate())}T${pad(h)}${pad(m)}00`;
      const title = `${labels.take}: ${entry.medicine}${entry.amount ? ` (${entry.amount})` : ''}`;
      const notes = [
        entry.food_note && `${labels.food}: ${entry.food_note}`,
        !entry.duration_days && labels.noDuration,
        labels.disclaimer,
      ].filter(Boolean).join('\n');

      lines.push(
        'BEGIN:VEVENT',
        `UID:hb-${now.getTime()}-${i}-${slot}@healthbridge`,
        `DTSTAMP:${stamp(now)}`,
        `DTSTART:${local}`,
        'DURATION:PT10M',
        `RRULE:FREQ=${entry.weekly ? 'WEEKLY' : 'DAILY'};COUNT=${occurrences}`,
        `SUMMARY:${escape(title)}`,
        `DESCRIPTION:${escape(notes)}`,
        'BEGIN:VALARM',
        'ACTION:DISPLAY',
        `DESCRIPTION:${escape(title)}`,
        'TRIGGER:PT0M',
        'END:VALARM',
        'END:VEVENT',
      );
      count += 1;
    });
  });

  lines.push('END:VCALENDAR');
  return { ics: lines.join('\r\n'), count };
}

export function downloadFile(content, filename, type) {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
