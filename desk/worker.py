"""Executed inside the restricted coding container, never on the host."""
import contextlib
import csv
import io
import json
import os
from pathlib import Path
import runpy
import sys
import time

import mysql.connector

HOME = Path('/home/coder/coursework')
ROW_LIMIT = 500


def connect():
    return mysql.connector.connect(host='127.0.0.1', user=os.environ['MYSQL_USER'],
        password=os.environ['MYSQL_PASSWORD'], database=os.environ['MYSQL_DATABASE'],
        connection_timeout=8, autocommit=True)


def quote(value):
    return '`' + value.replace('`', '``') + '`'


def value(item):
    if isinstance(item, bytes):
        return '0x' + item[:8192].hex() + ('… [truncated]' if len(item)>8192 else '')
    if isinstance(item, (int, float)) and not isinstance(item, bool):
        # JavaScript cannot represent large MySQL integers exactly.
        if isinstance(item, int) and abs(item) > 2**53 - 1:
            return str(item)
        return item
    if item is None or isinstance(item, bool):
        return item
    text=str(item)
    return text[:16384] + ('… [truncated]' if len(text)>16384 else '')


def columns(cursor):
    aliases={'LONG':'INT','LONGLONG':'BIGINT','SHORT':'SMALLINT','TINY':'TINYINT',
             'VAR_STRING':'VARCHAR','STRING':'CHAR','NEWDECIMAL':'DECIMAL'}
    return [{'name': d[0], 'type': aliases.get(mysql.connector.FieldType.get_info(d[1]),
                         mysql.connector.FieldType.get_info(d[1]) or str(d[1]))}
            for d in cursor.description or []]


def pack_rows(rows, budget=2500000):
    packed=[]
    limited=False
    for row in rows:
        if limited:
            continue
        converted=[value(v) for v in row]
        cost=len(json.dumps(converted,default=str).encode())
        if cost>budget:
            limited=True
            continue
        budget-=cost
        packed.append(converted)
    return packed, limited


def schema(db):
    with db.cursor(dictionary=True) as c:
        c.execute('SELECT TABLE_NAME AS name, TABLE_TYPE AS kind, TABLE_ROWS AS estimatedRows '
                  'FROM information_schema.TABLES WHERE TABLE_SCHEMA=%s ORDER BY TABLE_NAME', (db.database,))
        tables = c.fetchall()
        c.execute('SELECT TABLE_NAME AS tableName, COLUMN_NAME AS name, COLUMN_TYPE AS type, '
                  'IS_NULLABLE AS nullable, COLUMN_KEY AS keyKind, COLUMN_DEFAULT AS defaultValue, '
                  'EXTRA AS extra FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=%s '
                  'ORDER BY TABLE_NAME, ORDINAL_POSITION', (db.database,))
        fields = c.fetchall()
        c.execute('SELECT TABLE_NAME AS tableName, COLUMN_NAME AS columnName, '
                  'REFERENCED_TABLE_NAME AS targetTable, REFERENCED_COLUMN_NAME AS targetColumn '
                  'FROM information_schema.KEY_COLUMN_USAGE WHERE TABLE_SCHEMA=%s '
                  'AND REFERENCED_TABLE_NAME IS NOT NULL', (db.database,))
        relations = c.fetchall()
        c.execute('SELECT VERSION()')
        version = c.fetchone()['VERSION()']
    for table in tables:
        table['columns'] = [f for f in fields if f['tableName'] == table['name']]
        table['relations'] = [r for r in relations if r['tableName'] == table['name']]
    return {'database': db.database, 'version': version, 'tables': tables}


def table_info(db, name):
    match = next((t for t in schema(db)['tables'] if t['name'] == name), None)
    if not match:
        raise ValueError('That table no longer exists. Refresh the database browser.')
    return match


def table_rows(db, request):
    info = table_info(db, request['table'])
    table = quote(info['name'])
    names = [f['name'] for f in info['columns']]
    limit = max(1, min(100, int(request.get('limit', 100))))
    offset = max(0, min(10000000, int(request.get('offset', 0))))
    search = str(request.get('search', ''))[:200]
    where, args = '', []
    if search:
        pattern = '%' + search.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_') + '%'
        where = ' WHERE ' + ' OR '.join('CAST(' + quote(n) + ' AS CHAR) LIKE %s' for n in names)
        args = [pattern] * len(names)
    order = request.get('sort')
    if order not in names:
        order = next((f['name'] for f in info['columns'] if f['keyKind'] == 'PRI'), None)
    direction = 'DESC' if request.get('direction') == 'DESC' else 'ASC'
    ordering = ' ORDER BY ' + quote(order) + ' ' + direction if order else ''
    with db.cursor() as c:
        c.execute('SELECT COUNT(*) FROM ' + table + where, tuple(args))
        total = c.fetchone()[0]
        c.execute('SELECT * FROM ' + table + where + ordering + ' LIMIT %s OFFSET %s', tuple(args + [limit, offset]))
        packed,limited=pack_rows(c)
        result = {'columns': columns(c), 'rows': packed, 'truncated':limited,
                  'total': total, 'offset': offset, 'limit': limit, 'table': info}
    return result


def update_cell(db, request):
    info = table_info(db, request['table'])
    primary = [f['name'] for f in info['columns'] if f['keyKind'] == 'PRI']
    field = next((f for f in info['columns'] if f['name'] == request['column']), None)
    if not primary or not field or 'GENERATED' in field['extra']:
        raise ValueError('Editing needs a primary key and a writable column. Use SQL for this table.')
    keys = request.get('keys', {})
    if set(keys) != set(primary):
        raise ValueError('The row identity has changed. Reload its table first.')
    # Compare the original value as well as the primary key: never overwrite a
    # concurrent edit from Python or another query silently.
    where = ' AND '.join(quote(k) + ' <=> %s' for k in primary)
    sql = 'UPDATE ' + quote(info['name']) + ' SET ' + quote(field['name']) + '=%s WHERE ' + where
    sql += ' AND ' + quote(field['name']) + ' <=> %s LIMIT 1'
    with db.cursor() as c:
        c.execute(sql, tuple([request.get('value')] + [keys[k] for k in primary] + [request.get('original')]))
        if c.rowcount != 1:
            raise ValueError('This row changed, was removed, or already has that value. Reload before editing.')
    return {'updated': True}


def file_path(name):
    if not isinstance(name, str) or not name or len(name) > 240:
        raise ValueError('Choose a file name inside coursework.')
    path = (HOME / name).resolve()
    if not path.is_relative_to(HOME.resolve()) or path == HOME.resolve():
        raise ValueError('Files must stay inside coursework.')
    if any(part.startswith('.') for part in Path(name).parts):
        raise ValueError('Use a visible coursework file name.')
    return path


def files(request):
    action = request['op']
    if action == 'files':
        return {'files': sorted(str(p.relative_to(HOME)) for p in HOME.rglob('*')
            if p.is_file() and not any(x.startswith('.') for x in p.relative_to(HOME).parts)
            and p.suffix.lower() in {'.sql', '.py', '.txt', '.md', '.csv', '.json'})[:1000]}
    path = file_path(request['name'])
    if action == 'read':
        if path.stat().st_size > 1024 * 1024:
            raise ValueError('This file is larger than the editor’s 1 MB limit. Open it in the full code editor.')
        return {'name': request['name'], 'text': path.read_text()}
    if action == 'save':
        text = request['text']
        if not isinstance(text, str) or len(text.encode()) > 1024 * 1024:
            raise ValueError('Files can contain up to 1 MB of text.')
        path.parent.mkdir(parents=True, exist_ok=True)
        if request.get('createOnly') and path.exists():
            raise ValueError('A file with that name already exists. Choose another name.')
        if 'expectedText' in request and path.exists() and path.read_text() != request['expectedText']:
            raise ValueError('This file changed in another editor. Reopen it before saving over those changes.')
        temporary = path.with_name('.' + path.name + '.study-tmp')
        temporary.write_text(text)
        temporary.replace(path)
        return {'saved': True, 'name': request['name']}
    raise ValueError('Unknown file action')


class Output(io.StringIO):
    def __init__(self):
        super().__init__()
        self.truncated=False
    def write(self, text):
        available = max(0, 120000 - self.tell())
        if len(text)>available:
            self.truncated=True
        super().write(text[:available])
        return len(text)


def execute(request):
    started = time.monotonic()
    results = []
    remaining = 3000000
    db = connect()
    print(json.dumps({'pid': os.getpid(), 'connectionId': db.connection_id}), flush=True)
    try:
        with db.cursor() as c:
            c.execute(request['sql'], map_results=True)
            while True:
                if len(results) >= 100:
                    raise ValueError('Run up to 100 statements at once. Split a longer script into parts.')
                result = {'statement': c.statement[:3000], 'columns': columns(c), 'rows': [],
                          'affected': c.rowcount, 'warnings': c.warning_count, 'truncated': False}
                if c.with_rows:
                    if len(result['columns'])>256:
                        raise ValueError('This result has more than 256 columns. Select the columns you need to preview.')
                    budget=min(2500000,max(0,remaining-80000))
                    count=0
                    while True:
                        row=c.fetchone()
                        if row is None:
                            break
                        count+=1
                        if count<=ROW_LIMIT and budget>0:
                            converted=[value(v) for v in row]
                            cost=len(json.dumps(converted,default=str).encode())
                            if cost<=budget:
                                result['rows'].append(converted)
                                budget-=cost
                            else:
                                budget=0
                    result['truncated']=count>len(result['rows'])
                    result['previewLimit']=len(result['rows']) if len(result['rows'])<min(count,ROW_LIMIT) else ROW_LIMIT
                    result['rowCount'] = count
                results.append(result)
                remaining-=len(json.dumps(result,default=str).encode())
                if remaining<0:
                    raise ValueError('The result preview reached its size limit. Run fewer statements or select smaller values.')
                if not c.nextset():
                    break
        pending = db.in_transaction
        if pending:
            db.rollback()
        return {'results': results, 'elapsed': round((time.monotonic() - started) * 1000),
                'rolledBack': pending, 'mode': 'autocommit'}
    except Exception as exc:
        db.rollback()
        return {'results': results, 'error': str(exc), 'errno': getattr(exc, 'errno', None),
                'elapsed': round((time.monotonic() - started) * 1000), 'mode': 'autocommit'}
    finally:
        db.close()


def main(request):
    op = request['op']
    if op == 'state':
        path = HOME / '.study-desk-ui.json'
        if 'value' in request:
            encoded = json.dumps(request['value'])
            if len(encoded.encode()) > 700000:
                raise ValueError('Workspace preferences are too large. Export old queries and clear history.')
            temp = HOME / '.study-desk-ui.tmp'
            temp.write_text(encoded)
            temp.replace(path)
            return {'saved': True}
        try:
            return {'value': json.loads(path.read_text())}
        except (FileNotFoundError, ValueError):
            return {'value': None}
    if op in {'files', 'read', 'save'}:
        return files(request)
    if op == 'python':
        path = file_path(request['name'])
        if path.suffix != '.py':
            raise ValueError('Save your Python code as a .py file before running it.')
        print(json.dumps({'pid': os.getpid()}), flush=True)
        output = Output()
        import traceback
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            try:
                os.chdir(HOME)
                # The isolated interpreter still permits coursework modules.
                sys.path.insert(0, str(HOME))
                runpy.run_path(str(path), run_name='__main__')
                error = False
            except SystemExit as exc:
                error = exc.code not in (None, 0)
                if error:
                    print('Python exited with status', exc.code)
            except BaseException:
                traceback.print_exc()
                error = True
        return {'output': output.getvalue()+('\n[Output limited to 120,000 characters. Use the full editor terminal for longer output.]' if output.truncated else ''),
                'error': 'Python exited with an error.' if error else None}
    if op == 'execute':
        return execute(request)
    with connect() as db:
        if op == 'bootstrap':
            return {**schema(db), **files({'op': 'files'})}
        if op == 'schema':
            return schema(db)
        if op == 'table':
            return table_rows(db, request)
        if op == 'update':
            return update_cell(db, request)
        if op == 'kill':
            with db.cursor() as c:
                c.execute('KILL CONNECTION ' + str(int(request['connectionId'])))
            return {'cancelled': True}
    raise ValueError('Unknown workspace operation')


if __name__ == '__main__':
    try:
        print(json.dumps(main(json.load(sys.stdin)), default=str, allow_nan=False), flush=True)
    except Exception as exc:
        print(json.dumps({'error': str(exc), 'errno': getattr(exc, 'errno', None)}), flush=True)
