# GitHub Pages migration checks

Passed locally:

- Static build uses the supplied OWNER/REPOSITORY identity and rejects malformed values.
- Only index.html and .nojekyll are emitted into the Pages artifact.
- Desktop and tablet Chromium layouts render without horizontal page overflow.
- Create my workspace points to codespaces.new for the actual build identity.
- No ChatGPT-hosted URLs or local-download links are present on the public front page.
- Private workspace addresses save, survive reload, and can be forgotten.
- Invalid/non-HTTPS addresses are rejected.
- Python/JSON sources, inline JavaScript, and workflow syntax validate.
- The workflow grants the Pages/OIDC permissions and uploads dist/ only.

The browser editor/runtime is carried over from the tested Study Desk launcher:
SQL/MySQL integration, Python debugging, save/reload, automatic editor sign-in,
and extension/network restrictions were validated in the previous runtime tests.

Published and verified on GitHub Pages at the repository's current custom-domain
path. The Actions workflow deploys the built interface, rather than the README.

Automatic boot handoff checks (`python3 tests/test_boot_browser.py -v`):

- Preparing and checking states stay on the progress screen.
- Readiness automatically replaces setup with the editor, without a button click.
- Setup errors stay visible and retry resumes the automatic handoff.
- Readiness navigation also works inside an embedded preview frame.
- The optional `?stay=1` diagnostic view remains open after readiness.
- Blocked local/session storage receives an in-memory preference store; available
  browser storage and its saved preferences are left intact.

The devcontainer now starts the launcher in the foreground after browser attach,
prints a localhost URL for port detection, and uses the documented `openPreview`
port action rather than opening a new tab before the client connects.

The actual code-server handoff was also checked at desktop size and inside a
cross-site tablet preview with third-party storage blocked. Its own CSP nonce
allows the small storage fallback without relaxing the editor's CSP.
An earlier full code-server/MySQL trial exceeded this executor's local disk.
For the new SQL workspace, a disposable real MySQL 8.4 server and a lightweight
restricted Python container ran the actual Docker-exec worker/API. This avoids
duplicating the large code-server filesystem during these checks. It validates
the real database/worker, but is not a fresh end-to-end Codespaces provisioning.

Actual first-time Codespaces provisioning, iPad Safari, and the school network
still require a pilot. Existing Codespaces retain their old checkout and
container configuration; use a fresh Codespace to test this revised boot flow.

## SQL workspace checks

- Five statement-selection tests cover quoted semicolons, MySQL comment rules,
  delimiter-based routines, current statements and trailing whitespace.
- Six real MySQL/container integration tests cover scripts and errors, decimals
  and exact big integers, browsing/search, optimistic cell edits, explicit commit
  and rollback, saved files/preferences, path confinement, Python accessing the
  same database, cancellation, overlap rejection, preview limits and paging.
- The full browser pilot runs SQL through the toolbar, selects individual result
  sets, runs a selection/current statement, edits and searches a table, views its
  structure, downloads CSV, applies all 20 looks, runs a saved Python/MySQL file,
  restores tabs/theme after reload and rejects missing-token API requests.
- Additional real-browser checks cover actual schema completion, SQL formatting,
  EXPLAIN plans, the table designer's generated SQL, safe HTML/text rendering,
  result inspection, readable MySQL errors, and desktop/tablet/phone layouts.
- The six automatic-boot checks still pass with `/desk/` as the ready target.
- Python/shell/browser syntax and whitespace checks pass. CI now checks the SQL
  tests and rebuilds the committed bundle before deploying the public start page.

Run the real integration tests only against a disposable test runtime:
`DESK_INTEGRATION=1 python3 tests/test_desk_integration.py -v`.
The browser pilot is `python3 tests/test_desk_browser.py` with the test launcher
running on localhost:8787 (or set `DESK_BROWSER_URL`). It creates sample tables
and files and edits the sample rows.
