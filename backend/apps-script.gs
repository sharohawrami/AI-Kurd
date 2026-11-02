/**
 * Kurdistan AI Safety Hub: form backend (Google Apps Script).
 *
 * Receives submissions from the cohort application, the staff application and
 * the mailing-list form, writes each to its own tab in a Google Sheet, emails
 * the team, and sends applicants a confirmation email.
 *
 * Setup (about 10 minutes): see "Connecting the forms" in README.md.
 */

// 1. The ID of your Google Sheet: the long string in its URL between /d/ and /edit.
const SHEET_ID = 'PASTE_YOUR_SPREADSHEET_ID_HERE';

// 2. Where new-application alerts go. Leave '' to turn alerts off.
const NOTIFY_EMAIL = '';

// 3. Send applicants a confirmation email (uses your Gmail daily quota).
const SEND_CONFIRMATIONS = true;

// 4. Dates quoted in the confirmation emails. Keep these in step with site.json.
const DATES = {
  interviews_from: '[date]',
  interviews_to: '[date]',
  decisions_date: '[date]',
  reply_days: '14'
};

// The same dates written in Kurdish, for confirmation emails to Kurdish-language applicants.
const DATES_KU = {
  interviews_from: '[بەروار]',
  interviews_to: '[بەروار]',
  decisions_date: '[بەروار]',
  reply_days: '١٤'
};

const PROGRAM_NAME = 'KAISH Introduction Program';
const PROGRAM_NAME_KU = 'پرۆگرامی ناساندنی KAISH';
const HUB_KU = 'ناوەندی کوردستان بۆ سەلامەتیی زیرەکیی دەستکرد';
const FORMS = ['cohort', 'staff', 'newsletter'];
const MAX_CELL = 5000;

function doPost(e) {
  const lock = LockService.getScriptLock();
  lock.waitLock(20000);
  try {
    const data = JSON.parse(e.postData.contents);
    const form = String(data.form || '');
    if (FORMS.indexOf(form) === -1) return reply({ ok: false, error: 'Unknown form.' });
    if (data.website) return reply({ ok: true }); // spam trap filled in: accept silently, store nothing

    const fields = data.fields || {};
    const row = Object.assign({ received_at: new Date().toISOString() }, fields);
    const sheet = sheetFor(form);
    appendRow(sheet, row);

    if (form !== 'newsletter') {
      if (NOTIFY_EMAIL) notifyTeam(form, fields, sheet);
      if (SEND_CONFIRMATIONS && isEmail(fields.email)) confirmApplicant(form, fields);
    }
    return reply({ ok: true });
  } catch (err) {
    return reply({ ok: false, error: 'Could not save the submission.' });
  } finally {
    lock.releaseLock();
  }
}

function doGet() {
  return reply({ ok: true, service: 'Kurdistan AI Safety Hub forms' });
}

function sheetFor(name) {
  const book = SpreadsheetApp.openById(SHEET_ID);
  return book.getSheetByName(name) || book.insertSheet(name);
}

// Adds any new question as a new column, so the sheet follows the form.
function appendRow(sheet, row) {
  const lastCol = sheet.getLastColumn();
  const headers = lastCol ? sheet.getRange(1, 1, 1, lastCol).getValues()[0] : [];
  Object.keys(row).forEach(function (key) {
    if (headers.indexOf(key) === -1) headers.push(key);
  });
  sheet.getRange(1, 1, 1, headers.length).setValues([headers]).setFontWeight('bold');
  sheet.setFrozenRows(1);
  sheet.appendRow(headers.map(function (h) { return clean(row[h]); }));
}

// Stops spreadsheet formula injection and caps very long answers.
function clean(value) {
  if (value === undefined || value === null) return '';
  let s = String(value).slice(0, MAX_CELL);
  if (/^[=+\-@\t\r]/.test(s)) s = "'" + s;
  return s;
}

function isEmail(s) {
  return typeof s === 'string' && /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(s);
}

function notifyTeam(form, f, sheet) {
  const what = form === 'cohort' ? 'Cohort 1 application' : 'Team application (' + (f.roles || 'no role') + ')';
  MailApp.sendEmail({
    to: NOTIFY_EMAIL,
    subject: 'New ' + what + ': ' + (f.full_name || 'unnamed'),
    body: 'A new ' + what + ' has arrived from ' + (f.full_name || 'an applicant') + ' (' + (f.email || 'no email') + ').\n\n' +
          'Open the sheet: ' + sheet.getParent().getUrl() + '#gid=' + sheet.getSheetId()
  });
}

function confirmApplicant(form, f) {
  const kurdish = String(f.language || '').indexOf('Kurdish') === 0;
  const first = String(f.full_name || '').trim().split(/\s+/)[0] || (kurdish ? 'هاوڕێ' : 'there');
  let subject, body;
  if (kurdish && form === 'cohort') {
    subject = 'داواکارییەکەت گەیشت: ' + PROGRAM_NAME_KU + '، خولی یەکەم';
    body = 'سڵاو ' + first + '،\n\n' +
      'سوپاس بۆ پێشکەشکردنی داواکاری بۆ خولی یەکەمی ' + PROGRAM_NAME_KU + '. هەنگاوەکانی داهاتوو ئەمانەن:\n\n' +
      '١. گفتوگۆ لەگەڵ ڕێکخەرانی دانیشتن لە نێوان ' + DATES_KU.interviews_from + ' و ' + DATES_KU.interviews_to + ' دەبێت.\n' +
      '٢. هەموو داواکاران تا ' + DATES_KU.decisions_date + ' بڕیارەکە وەردەگرن.\n\n' +
      'ئەگەر هەر شتێک لە داواکارییەکەتدا گۆڕا، وەڵامی ئەم ئیمەیڵە بدەرەوە.\n\n' +
      'تیمی ' + HUB_KU + ' (KAISH)\n' +
      'دەستپێشخەرییەکی ئەکادیمییە و پەیوەستە بە AI Kurd';
  } else if (kurdish) {
    subject = 'داواکارییەکەت بۆ بەشداربوون لە تیمی ' + HUB_KU;
    body = 'سڵاو ' + first + '،\n\n' +
      'سوپاس بۆ داواکارییەکەت بۆ بەشداربوون لە تیمی ناوەندەکەمان. خۆمان هەموو داواکارییەک دەخوێنینەوە و لە ماوەی ' +
      DATES_KU.reply_days + ' ڕۆژدا وەڵامت دەدەینەوە.\n\n' +
      'ئەگەر ویستمان قسە بکەین، بەستەرێکت بۆ دەنێرین بۆ دیاریکردنی کاتی گفتوگۆیەکی ٣٠ خولەکی. ئەگەر لەم ماوەیەدا شتێک گۆڕا، تەنها وەڵامی ئەم ئیمەیڵە بدەرەوە.\n\n' +
      'تیمی ' + HUB_KU + ' (KAISH)\n' +
      'دەستپێشخەرییەکی ئەکادیمییە و پەیوەستە بە AI Kurd';
  } else if (form === 'cohort') {
    subject = "We've received your application: " + PROGRAM_NAME + ', Cohort 1';
    body = 'Hi ' + first + ',\n\n' +
      'Thank you for applying to Cohort 1 of the ' + PROGRAM_NAME + ". Here's what happens next:\n\n" +
      '1. Conversations with facilitators take place between ' + DATES.interviews_from + ' and ' + DATES.interviews_to + '.\n' +
      '2. Every applicant receives a decision by ' + DATES.decisions_date + '.\n\n' +
      'If anything in your application changes, reply to this email.\n\n' +
      'The Kurdistan AI Safety Hub team (KAISH)\n' +
      'An academic initiative affiliated with AI Kurd';
  } else {
    subject = 'Your application to join the Kurdistan AI Safety Hub team';
    body = 'Hi ' + first + ',\n\n' +
      'Thank you for applying to join the Kurdistan AI Safety Hub as ' + (f.roles || 'a team member') + '. ' +
      'We read every application ourselves and will reply within ' + DATES.reply_days + ' days.\n\n' +
      "If we'd like to talk, we'll send a link to book a 30-minute call. If anything changes in the meantime, just reply to this email.\n\n" +
      'The Kurdistan AI Safety Hub team (KAISH)\n' +
      'An academic initiative affiliated with AI Kurd';
  }
  const options = NOTIFY_EMAIL ? { replyTo: NOTIFY_EMAIL } : {};
  MailApp.sendEmail(f.email, subject, body, options);
}

function reply(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}
