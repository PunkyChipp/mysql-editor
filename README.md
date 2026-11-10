# Study Desk — SQL and Python at one website address

**https://highereconomicsrevision.co.uk/mysql-editor/** serves the actual editor.
It stays at that address. GitHub Pages hosts the interface; an authenticated,
same-origin API gateway connects to real MySQL and Python on the owner's Windows
PC over an outbound Cloudflare Tunnel. School devices need only a browser.

Until the home PC and route are activated, the page explicitly reports that its
backend is not connected. It does not simulate a working MySQL connection.

## Windows owner setup

The [published owner guide](https://highereconomicsrevision.co.uk/mysql-editor/setup/)
includes the package download and account/DNS instructions.

1. Install Python 3.12+ and Docker Desktop; complete Docker's first-run/WSL setup.
2. Extract the package into a permanent folder in your own Documents folder.
   Open **START STUDY DESK.cmd** to open the local setup window.
3. Create your workspace username and a unique password of at least 12 characters.
   The launcher prepares the coding runtime, MySQL and persistent coursework.
4. Activate the existing domain on Cloudflare's free plan. Import and verify all
   existing DNS records before changing nameservers at the registrar. Preserve
   GitHub Pages records, email records and working HTTPS. This owner-account step
   cannot be performed by a static website or the GitHub connector.
5. Enter a scoped Cloudflare API token only in the local setup window. Review the
   changes and choose Connect website. It creates the tunnel, installs the official
   checksum-verified connector, uploads the API Worker and adds the narrow route.
   The Cloudflare API token is discarded after setup.
6. Wait for the public connection test to succeed, then sign into the editor.
   Test the same link and SELECT 1 from school Wi-Fi before depending on it.

Optional startup at Windows sign-in and keep-awake are configured locally.
Keep-awake does not change the permanent power plan or keep the display on.
The PC and Docker must remain running. Disconnect website stops remote access
without deleting coursework; local Docker containers may remain running.

## Routing and the existing website

| Component | Location |
| --- | --- |
| Complete editor, 20 looks, five layouts | GitHub Pages /mysql-editor/ |
| Browser login and database requests | Same website origin /mysql-editor/api/* |
| API proxy and outbound tunnel | Owner's Cloudflare account / Windows PC |
| Real MySQL, Python and coursework | Restricted Docker runtime on Windows PC |

Only the API path is routed through the Worker. The economics site files stay
on GitHub Pages. The installer adds one origin CNAME and enables Cloudflare
proxying on existing website records without changing their addresses. It does
not reset DNS, change registrar nameservers, edit email records or overwrite an
unrelated Worker. Domain activation must preserve all existing DNS records.

## Editor and authentication

SQL is the main workspace: query tabs, schema completion, statement/selection/
script execution, multiple results, formatting, EXPLAIN plans, table search and
paging, optimistic cell edits, a SQL-generating table designer, CSV and history.
Python connects to the same database. VS Code Dark is the default. See the
[workspace guide](desk/README.md) for execution and persistence rules.

The public app includes SQL and noninteractive Python. The full code-server
terminal/debugger is a local owner tool; its automatic sign-in proxy is never
exposed by the remote API. Additional runtimes require administrator setup.

Passwords use PBKDF2-SHA256 with random salts and 600,000 iterations. Eight-hour
revocable sessions use Secure, HttpOnly, SameSite=Strict cookies scoped to the
API path. Origin/CSRF checks, login throttling, bounded requests and an independent
Worker-to-origin secret protect the service. Browser requests stay same-origin.

SQL/Python executes only inside the existing restricted Docker runtime through
fixed commands and JSON stdin. No external network, writable system/extensions,
Docker socket or Linux capabilities are provided to that coding container.
Connector credentials and origin secrets are stored in the Windows user's
LocalAppData/StudyDesk folder. Private state, .env files and logs are excluded
from public artifacts and downloads. Export backups before deleting volumes.

This provisions one personal workspace, not isolated classroom accounts/runtimes.
Do not share one account as a substitute for multi-user isolation. School filtering
and actual iPad Safari still require a pilot. Provider free-plan limits apply;
setup does not select a paid plan.

## Development

Run npm ci and npm run build to rebuild the committed browser bundle. npm test
checks SQL scope selection and the Worker. Python tests cover authentication,
sessions, CSRF, owner setup, DNS preservation, checksums, packaging and startup.
Real database/browser pilots are documented in TESTS.md.

python3 scripts/build_pages.py --repository PunkyChipp/mysql-editor creates the
public editor, guide and reviewed Windows package in dist/. CI checks the sources
before Pages publication. The older local/Codespaces launcher remains available
for development; it is not the published website's execution backend.
