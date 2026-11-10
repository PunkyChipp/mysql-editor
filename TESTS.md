# GitHub Pages migration checks

Passed locally:

- Static build uses the supplied OWNER/REPOSITORY identity and rejects malformed values.
- The real editor, relative assets, public configuration, owner guide and reviewed
  Windows home package are emitted into the Pages artifact; private state is excluded.
- Desktop and tablet Chromium layouts render without horizontal page overflow.
- The public editor uses /mysql-editor/api/ on its own origin and no Codespaces launch link.
- No ChatGPT-hosted URLs are used. The owner guide offers the reviewed home package.
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
- A preview shows an Open Study Desk link; following it opens a top-level tab.
- Both setup and SQL client guards leave frames before making database requests.
- The actual standalone workspace uses the full tablet browser viewport.
- Standalone links use the Codespace's private forwarding domain.
- The optional `?stay=1` diagnostic view remains open after readiness.
- Blocked local/session storage receives an in-memory preference store; available
  browser storage and its saved preferences are left intact.

The devcontainer starts a detached background launcher on host startup, waits for
its HTTP listener, then returns. Browser attach emits the localhost URL and the
documented `openBrowser` port action opens the app outside the IDE. A generated
start note contains the actual private address if the browser blocks the tab.
Three lifecycle tests cover detached startup, reattach reuse, the note and config.

Earlier code-server checks covered desktop and cross-site storage fallback.
The current launch flow opens the standalone app instead of embedding it.
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
- Ten automatic-boot/browser checks pass with `/desk/` as the standalone target.
- Python/shell/browser syntax and whitespace checks pass. CI now checks the SQL
  tests and rebuilds the committed bundle before deploying the public start page.

Run the real integration tests only against a disposable test runtime:
`DESK_INTEGRATION=1 python3 tests/test_desk_integration.py -v`.
The browser pilot is `python3 tests/test_desk_browser.py` with the test launcher
running on localhost:8787 (or set `DESK_BROWSER_URL`). It creates sample tables
and files and edits the sample rows.

## Same-domain home deployment (current public architecture)

- Ten origin API tests cover the Worker secret, password hashing, scoped Secure/
  HttpOnly cookies, CSRF and Origin enforcement, unknown routes/operations,
  session expiry/logout, login throttling, runtime readiness and current Docker health.
- Five Worker tests cover the narrow path/method allowlist, cross-origin rejection,
  secret injection/header sanitization, bounded request bodies, offline handling
  and no CORS exposure. Public HTTP is rejected before reaching the home origin.
- Five deployment/package tests cover inactive zones and route conflicts without
  mutations, preservation of existing website DNS addresses, relative static
  editor assets, secret-free packaging and failed connector checksum rejection. A failed local boot retries through its existing token-checked setup endpoint.
- Three local-wizard tests verify account hashing, no credential disclosure in
  status, local token/review requirements and actual setup-page delivery.
- A browser pilot exercised the actual Worker module as a same-origin edge adapter,
  the authenticated origin and a disposable real MySQL 8.4 runtime. It passed
  login rejection/success, real SQL scripts/results, Python/MySQL execution,
  saved files/theme/session restoration, logout and the public connection check.
  All browser requests stayed under /mysql-editor/ on the same test origin.

This pilot used a disposable lightweight restricted Python container with the
same worker dependencies, plus real MySQL, to fit this executor's disk limit.
It does not establish that a Windows host or live Cloudflare/registrar account
has been configured. Windows first-run, live DNS/tunnel activation, actual iPad
Safari and school Wi-Fi remain owner-side checks. No actual Cloudflare account
mutations were performed by the tests; provisioner transports were mocked.

Owner launch commands, the setup window and public guide are built. The GitHub
connector cannot log into the owner's Windows PC, Cloudflare or registrar.
