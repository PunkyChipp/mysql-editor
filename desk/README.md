# The SQL workspace

The public editor opens at `/mysql-editor/`, using a same-origin authenticated
API connected to the owner's Windows PC. It uses real MySQL. The local developer
launcher still serves `/desk/`; its full code-server editor remains at
`/?folder=/home/coder/coursework` for local debugging and terminals.

The public workspace runs in its own full browser tab, without visiting Codespaces.
Until its home backend is configured, the connection screen reports it as offline.
The owner setup guide and package are at `/mysql-editor/setup/`.

## Everyday use

- **Run query / Ctrl or Command Enter** runs selected text, or the statement at
  your cursor. **Ctrl or Command Shift Enter** runs the whole script.
- **Format** formats SQL. Completion knows MySQL keywords and the current schema.
- Click a table to browse its data. Expand the arrow for columns; use its code
  button to write a SELECT. Search and sort happen in MySQL. Browsing pages
  through 100 rows at a time.
- Double-click a cell in a base table with a primary key to edit it. The update
  checks its original value to catch concurrent changes. Generated columns and
  tables without primary keys use SQL instead of grid editing.
- **Explain** shows the MySQL JSON plan for a SELECT/WITH query, with table access
  and row estimates. It does not use EXPLAIN ANALYZE or execute the data changes.
- The **+** beside Tables opens a small table designer. Review its generated SQL
  and run it when you are ready. No table is created just by opening the designer.
- SQL results show multiple statement results separately. Previews display up to
  500 rows, with limits marked. Very large cells are marked as truncated.
  CSV and clipboard exports contain the displayed rows, not the whole table.
- Files saves real coursework files. Draft tabs, recent runs, appearance and
  layout also persist in the coursework volume. Importing a local SQL/Python
  text file opens it for review; it does not execute it.
- Python + MySQL example connects through the same environment variables and
  database as the SQL tabs. The small runner is noninteractive; use the full
  editor's terminal for input(), and its debugger for breakpoints. Other language
  runtimes/drivers require administrator installation.

## Appearance

VS Code Dark is the default. There are 20 bundled palettes, with Classic,
Rounded studio, Editorial, Signal and Compact terminal layouts. Layouts change
panel geometry, spacing, typography, tabs and surfaces. They can be mixed with
any palette. These controls style the SQL/Python workspace; the separate full
VS Code editor has its own theme settings. No theme requires an extension or
external request.

## Execution rules

Each run uses a fresh connection. Auto-commit is enabled. Put an entire explicit
transaction, including COMMIT, in one script. Unfinished transactions roll back
when that run ends; MySQL DDL can commit implicitly. If a later statement fails,
earlier auto-committed changes may remain. Stop and the 35-second execution limit
cannot undo changes that have already committed.

The host handles authenticated HTTP and invokes the approved worker inside the
restricted editor container via Docker exec, with JSON stdin and no shell.
Arbitrary SQL and Python never execute on the launcher host. No browser-supplied
connection credentials are accepted. The existing private forwarded-port rule,
read-only extension installation and no-external-network runtime still apply.

The API checks its per-launch token and Origin, confines files to coursework,
caps code and output sizes, rejects overlapping runs and supports cancellation.
This remains a private, one-person workspace, not a shared public SQL service.

## Frontend build

Students do not need Node or npm. The compiled bundle is committed and served
locally by the launcher, with no CDN dependencies. Developers can use `npm ci`
and `npm run build`; `npm test` checks statement selection. Backend and UI pilot
tests are under `tests/`. Bundled dependency licenses are in
`THIRD_PARTY_NOTICES.txt`.
