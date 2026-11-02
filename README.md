# Kurdistan AI Safety Hub website

The bilingual (English and Sorani Kurdish) website of the Kurdistan AI Safety Hub, with an admin panel. Admins sign in at `/login` and can:

- **Edit any text on any page, in both languages.** Either click straight on the page (**Edit this page** in the bar at the bottom), or use **Pages and text** in the admin panel for texts you can't click on (the browser-tab title, search-engine descriptions, button labels, form placeholders, error messages).
- **Post news and events with pictures.** They appear on the homepage ("From the Hub") and on `/news`, each with its own page. Until the first post, the homepage shows empty woven picture frames.
- **Change dates and details.** These include the deadline, venue, emails and team names. Each change updates every page that uses it.
- **Read applications.** Cohort, team and mailing-list submissions are stored in the database and can be downloaded as a spreadsheet.
- **Manage admins** (superadmins only). They can add admins, make someone a superadmin, reset passwords, deactivate or delete accounts.
- **Show and hide.** Hide any section of any page, any part of the header and footer, or a whole page, without deleting it. Use **Hide** on the page in edit mode, or the **Show and hide** page in the admin panel. Visitors don't see hidden parts (links to hidden pages are removed too); admins see them faded in edit mode and can show them again at any time.
- **Universities.** Give each university one page (a name can be added only once) with its own representatives' sign-in. See [Universities](#universities).

**Visitors** can also create a free member account from the **Register** button in the header (both languages), sign in, and keep a private profile: their picture in a woven medallion frame, their name in Kurdish script, what they do, their city, a few sentences about themselves and the parts of AI safety they care about. Only the member and the Hub team can see a profile. Member accounts can never open the admin panel; admins are a separate list that only a superadmin can add to.

English pages live at `/`, Kurdish pages at `/ku/` (right to left).

## First sign-in

The database in `instance/kaish.db` already has one account:

| Username | Role |
| --- | --- |
| `sharo` | Superadmin |

The one-time password was given to you separately. At first sign-in you must choose your own password (at least 10 characters). Then go to **Admins** to add other people. Each new admin gets a one-time password that you pass on to them.

Lost the password? On the server, run `python manage.py reset-password sharo` to get a new one-time password.

## Run it on your computer

Requires Python 3.10 or newer.

```
pip install -r requirements.txt
python app.py
```

Open http://localhost:8000. The admin panel is at http://localhost:8000/login.

## Member accounts

| Page | What it does |
| --- | --- |
| `/register`, `/ku/register` | Create an account: name, email, optional city, password (at least 10 characters) and agreement to the privacy notice. |
| `/signin`, `/ku/signin` | Sign in. Five wrong passwords lock that email for 15 minutes. |
| `/profile`, `/ku/profile` | The member's own profile, laid out like a carpet. |
| `/profile/edit` | Change the picture (cropped to a square), details, interests, preferred language and password, or delete the account. |

In the admin panel, **Members** lists everyone who registered, with search. From a member's page an admin can give a temporary password (for "I forgot my password"), pause the account or delete it. **Pause registration** on the Members page closes the Register form without affecting existing members.

Member pictures are private: they're served only to that member and to signed-in admins, never as public files. All wording on the sign-in, registration and profile pages, including every error message, can be edited like any other page under **Pages and text**.

## Universities

In the admin panel, **Universities** → **Add a university** creates a draft page. Fill in its details and logo, tick **Published on the website**, then add one or more **representatives** on the same page. Each gets a one-time password, like a new admin.

Representatives sign in at `/login` and see only their own **University panel**. There they can:

- edit their university's page (name, city, website, logo, about text, in both languages);
- post news and events, which appear on their university's page and not on the Hub's homepage;
- open courses, each with its own page and application form. They choose the questions: short or long answers, one or several choices, and the weekly availability table. Applications arrive in the panel, with a summary of when applicants are free, and can be downloaded as a spreadsheet. A form closes by itself after its deadline.

They can't open anything else in the admin panel. Hub admins can see and change everything. Public addresses: `/universities`, `/universities/NAME`, `/universities/NAME/courses/COURSE` (and the same under `/ku/`).

## Put it online

The site needs a host that runs Python and keeps files between restarts. Accounts, edits, pictures and applications live in the data folder (`instance/` by default, or wherever `KAISH_DATA_DIR` points). **Back up that folder.**

**Any Linux server (VPS) or Docker host:**

```
docker build -t kaish .
docker run -d -p 8000:8000 -v kaish-data:/data --restart unless-stopped kaish
```

On first start, the database with the `sharo` account is copied into the `kaish-data` volume. Put a web server with HTTPS in front of it, such as Caddy (`caddy reverse-proxy --from kaish.org --to localhost:8000`) or nginx.

Without Docker: `pip install -r requirements.txt`, then `gunicorn -w 2 --threads 4 -b 127.0.0.1:8000 app:app` behind nginx or Caddy, with `KAISH_SECURE_COOKIES=1` and `KAISH_PROXY=1`.

**Render:** the repository includes `render.yaml`. In the Render dashboard choose **New → Blueprint**, pick the repository and confirm. That creates the web service (smallest paid instance, Frankfurt) with a 1 GB disk at `/data`. Don't use Render's free instance: it can't keep a disk, so every edit and account would be lost on restart.

**Railway or Fly.io:** deploy this folder as a Docker service and attach a persistent volume mounted at `/data`.

**PythonAnywhere:** upload the folder, create a Flask web app pointing at `app.py` (the WSGI object is `app`), and turn on "Force HTTPS".

## Settings (environment variables)

| Variable | What it does |
| --- | --- |
| `KAISH_DATA_DIR` | Where the database, pictures and session key are kept. Default `./instance`. |
| `KAISH_SECURE_COOKIES=1` | Sign-in cookies only over HTTPS. Turn on in production. |
| `KAISH_PROXY=1` | Trust the `X-Forwarded-*` headers from your nginx, Caddy or hosting platform. |
| `KAISH_SECRET_KEY` | Optional. Session signing key; otherwise one is generated in the data folder. |
| `KAISH_SMTP_HOST`, `KAISH_SMTP_PORT`, `KAISH_SMTP_USER`, `KAISH_SMTP_PASSWORD`, `KAISH_SMTP_FROM` | Email server for confirmation emails to applicants (in English or Kurdish, matching the form they used). |
| `KAISH_NOTIFY_EMAIL` | Optional. Also email the team about each new application. |
| `PORT`, `HOST` | For `python app.py` only. |

Without email settings, applications are still saved and shown in the admin panel, but applicants get no confirmation email. The dashboard warns about this. The application pages tell applicants a confirmation email is coming, so set up email before launch or edit that sentence.

## Security

- Passwords are stored as scrypt hashes and never shown again after they're created.
- Five wrong passwords for one username lock sign-in from that address for 15 minutes.
- Changing a password, resetting it or deactivating an account signs that account out everywhere.
- There is always at least one active superadmin: the last one can't be demoted, deactivated or deleted.
- Edited text is stored as plain text and escaped when shown, so nobody can inject code through the editor.
- Uploaded pictures are checked, re-encoded as WebP and resized to at most 1800 pixels.
- Spreadsheet downloads are protected against formula injection.

## Command-line tasks

```
python manage.py create-superadmin USERNAME --name "Full name"   # new superadmin with a one-time password
python manage.py reset-password USERNAME                          # new one-time password, also unlocks
python manage.py list-admins
python manage.py export                                           # static copy, see below
```

## Static copy (optional)

`python build.py` writes the whole site, with every saved edit and published post, as plain HTML to `dist/`. It can be hosted anywhere, such as Netlify or GitHub Pages, but it has no sign-in, editing, member accounts, university pages or application storage. To collect applications from a static copy, connect `backend/apps-script.gs`, a Google Sheets backend. Set its web-app address as `form_endpoint` in `site.json`, following the instructions at the top of that file.

## What's here

| Path | What it is |
| --- | --- |
| `app.py` | The web app: public pages, form submissions, sign-in, admin panel, member accounts and university pages. |
| `renderer.py`, `ornaments.py` | Turn page templates into finished pages; the kilim, medallion and pattern artwork. |
| `db.py`, `manage.py` | Database tables and command-line tasks. |
| `templates/admin/` | Admin panel pages. |
| `src/pages/`, `src/pages/ku/` | Original English and Kurdish page content. Edits made in the admin panel are stored separately, so these stay untouched. |
| `src/TRANSLATION_GUIDE.md` | Glossary and rules used for the Kurdish text. |
| `site.json` | Default dates, details and placeholder labels. Values changed in the admin panel take priority. |
| `assets/` | Design and behaviour: `site.css`, `site.js` for the public site; `admin.css`, `edit.css`, `edit.js` for admins. |
| `instance/kaish.db` | The database, with the `sharo` account. |
| `backend/apps-script.gs` | Google Sheets backend, only for the static copy. |

## Before launch

- Fill in **Dates and details**. The dashboard counts what's still empty; empty values show on the site as highlighted `[placeholders]`.
- Have a native Sorani speaker review the Kurdish pages. You can now fix any wording directly on the page.
- Check that the AI Kurd rows on the About page describe AI Kurd accurately, and that team names appear only for people who agreed.
- Read the privacy notice against how you'll actually store and delete applications and member accounts (both are in the database on your server).
- Set **Website address** in Dates and details, so search engines get the right links.
