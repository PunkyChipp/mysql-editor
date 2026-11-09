# Study Desk — GitHub Pages + a private browser workspace

The public start page lives on GitHub Pages. Create my workspace opens this
repository in the student's own Codespace. The devcontainer installs the host
prerequisites and starts the web app in a detached background process.
After browser attachment, private port 8787 opens in a full browser tab. Students
use a normal browser; no local installs, uploads, or setup commands are needed.

The editor, real MySQL server, and Python run in that GitHub-hosted computer.
Pages serves the front page. No ChatGPT-hosted website is needed.

The default editor is now the SQL-first workspace: visible run controls, query
tabs, database/schema browsing, editable data grids, query history, CSV export,
SQL formatting, EXPLAIN plans, Python integration and 20 bundled looks with five
layout styles. Standard VS Code Dark opens by default. Code editor opens the
full VS Code-style environment for debugging and terminals. See
[the workspace guide](desk/README.md) for controls and execution rules.

## Publication

Enable repository Pages with Source: GitHub Actions. The included workflow builds
the page using the actual repository name and publishes only dist/. Runtime
source, credentials, and coursework are not published as Pages assets. Every push
to main updates the front page. Initial Pages enablement needs repository admin
access; the workflow does not ask for a personal access token.

## Student flow

1. Open the Pages URL, choose Create my workspace, sign into GitHub, and approve creation.
2. Study Desk opens in a full browser tab, shows setup progress, and switches
   to its own editor when all checks pass. The backend does not depend on the
   IDE terminal staying attached.
3. Keep port 8787 PRIVATE. GitHub may require sign-in or an access approval;
   the application cannot accept those account prompts for you.
4. Bookmark the workspace or save its address on the start page.
5. Resume existing workspaces in GitHub. Stop them when finished to conserve allowance.

First launch takes several minutes. GitHub account, compute, storage, and usage
restrictions apply. Creating another Codespace creates another environment.

## Persistence and isolation

Saved files and MySQL data use Docker volumes. Export backups outside Codespaces
before deleting it or rebuilding its host container. Source commits do not
include inner coursework/database contents automatically. Each student has a
separate environment; this is not a shared multi-user server.

If your browser blocks the automatic tab, follow Open Study Desk in the generated
`.study-desk-start.md` note once. The Ports > 8787 > Open in Browser control also
opens the same independent web app. An embedded request receives an Open Study
Desk link instead of trying to load the workspace inside the frame.
The setup page accepts `?stay=1` to keep its diagnostic view open after readiness.
Saved coursework and MySQL data use the host's Docker volumes. The app has its
own browser URL and interface; Codespaces provides its computer. Keep that
Codespace running. Its normal inactivity and usage limits still apply.

The coding runtime has no external network and a read-only extension installation.
No AI extensions are installed. Ordinary completion, diagnostics, debugging,
SQLTools, and Python's MySQL connector are included. The outer Codespace remains
the owner's administration interface.

The launcher automatically signs into the inner editor, relying on localhost or
PRIVATE Codespaces forwarding. Do not expose the launcher as a public service.
The public Pages site contains no runtime passwords.

## Development

    python3 scripts/build_pages.py --repository OWNER/REPOSITORY
    python3 -m http.server 8808 --bind 127.0.0.1 --directory dist

The static build uses Python's standard library. On a Docker host, python3
launch.py opens the guided setup. The boot handoff has browser checks in
`tests/test_boot_browser.py` (requires Playwright and Chromium). Actual GitHub
provisioning and iPad Safari still need a one-account pilot before classroom use.
