# Sharing the app

The app holds A&M draft assessments of listed companies. Share it **inside A&M** only, and keep the DRAFT notice on everything you send.

| Option | Best for | How |
|---|---|---|
| **The repository** | A colleague who will run the app | They clone the private repository and switch to the branch you name. Send the `.env` (API key and resource settings) separately, through a password manager or an approved file share, never by email or in git. Then run `start_app.bat`, or follow the quick start in the README. |
| **Read-only snapshot** | A reader who only needs to view one assessment | From `frontend/`, run `node scripts/make_snapshot.mjs <company-id>`. It writes one self-contained HTML file with the report screens and the Word and HTML deliverables, and changes nothing stored. Download the file before opening it: SharePoint and OneDrive previews do not run scripts. |
| **Word report or interactive HTML** | A reader who needs the report itself | Download either from the app's report page. |

Do not use public hosting (public GitHub Pages, Netlify or similar): the content is proprietary draft material. Before sharing outside the core team, have a qualified A&M professional review the content.
