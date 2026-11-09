# Your coursework

Run `python main.py` in the terminal, or press F5 to debug it.
Run SQL with SQLTools, or in the terminal:

```sh
MYSQL_PWD="$MYSQL_PASSWORD" mysql -h127.0.0.1 -ustudent schoolwork < practice.sql
```

SQLTools: select the preconfigured Schoolwork connection. To recreate it, create a MySQL connection to 127.0.0.1, port 3306, database
schoolwork, username student. Use the STUDENT DATABASE PASSWORD from the
host's private .env file; ask the host administrator if someone else manages it.
Do not paste that file into coursework or commit it to Git.

Python completion and diagnostics come from BasedPyright. The Python debugger
and ordinary SQL tools are installed. Internet access and installing extra
extensions/packages are intentionally unavailable. Save work here: this folder
persists across container restarts. The home directory outside this folder does not.
