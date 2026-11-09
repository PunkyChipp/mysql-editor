"""Real MySQL/container API checks. Use a disposable test database/runtime.

Run with DESK_INTEGRATION=1 and COMPOSE_FILE/COMPOSE_PROJECT_NAME pointing to it.
"""
import json
import os
from pathlib import Path
import sys
import time
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from desk_api import DeskError, DeskService


@unittest.skipUnless(os.environ.get('DESK_INTEGRATION')=='1','Needs a disposable MySQL test runtime')
class DeskIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.service=DeskService()

    def sql(self,sql):
        started=self.service.start({'op':'execute','sql':sql})
        return self.wait(started['id'])

    def wait(self,identifier):
        deadline=time.monotonic()+45
        while time.monotonic()<deadline:
            job=self.service.status(identifier)
            if job['state']!='running':
                return job
            time.sleep(.1)
        self.fail('Run never completed')

    def test_01_mysql_scripts_results_types_and_errors(self):
        job=self.sql("DROP TABLE IF EXISTS desk_checks; CREATE TABLE desk_checks (id INT PRIMARY KEY, note VARCHAR(200), amount DECIMAL(10,2)); INSERT INTO desk_checks VALUES (1,'Alex',12.34),(2,NULL,99.90); SELECT * FROM desk_checks ORDER BY id; SELECT 9007199254740993 AS exact_integer;")
        self.assertEqual(job['state'],'done',job)
        results=job['result']['results']
        self.assertEqual(results[-2]['rows'],[[1,'Alex','12.34'],[2,None,'99.90']])
        self.assertEqual(results[-1]['rows'][0][0],'9007199254740993')
        error=self.sql('SELECT 1; THIS IS NOT SQL;')
        self.assertEqual(error['state'],'error')
        self.assertTrue(error['result']['error'])

    def test_02_table_browsing_and_optimistic_cell_update(self):
        table=self.service.call({'op':'table','table':'desk_checks','search':'Alex'})
        self.assertEqual(table['total'],1)
        self.assertEqual(table['rows'][0][1],'Alex')
        self.service.call({'op':'update','table':'desk_checks','column':'note','keys':{'id':1},'original':'Alex','value':'Sam'})
        with self.assertRaises(DeskError):
            self.service.call({'op':'update','table':'desk_checks','column':'note','keys':{'id':1},'original':'Alex','value':'stale'})
        self.assertEqual(self.service.call({'op':'table','table':'desk_checks','search':'Sam'})['total'],1)

    def test_03_transactions_roll_back_if_not_explicitly_committed(self):
        unfinished=self.sql("START TRANSACTION; INSERT INTO desk_checks VALUES (3,'rolled back',1.00);")
        self.assertTrue(unfinished['result']['rolledBack'])
        self.assertEqual(self.sql('SELECT COUNT(*) FROM desk_checks WHERE id=3')['result']['results'][0]['rows'][0][0],0)
        committed=self.sql("START TRANSACTION; INSERT INTO desk_checks VALUES (3,'committed',1.00); COMMIT;")
        self.assertEqual(committed['state'],'done')
        self.assertEqual(self.sql('SELECT COUNT(*) FROM desk_checks WHERE id=3')['result']['results'][0]['rows'][0][0],1)

    def test_04_code_and_preferences_persist_and_paths_are_confined(self):
        source="import os, mysql.connector\nwith mysql.connector.connect(host='127.0.0.1',user=os.environ['MYSQL_USER'],password=os.environ['MYSQL_PASSWORD'],database=os.environ['MYSQL_DATABASE']) as db:\n with db.cursor() as c:\n  c.execute('SELECT COUNT(*) FROM desk_checks')\n  print('Shared MySQL rows:', c.fetchone()[0])\n"
        self.service.call({'op':'save','name':'api-check.py','text':source})
        self.assertEqual(self.service.call({'op':'read','name':'api-check.py'})['text'],source)
        run=self.service.start({'op':'python','name':'api-check.py'})
        result=self.wait(run['id'])
        self.assertEqual(result['state'],'done',result)
        self.assertIn('Shared MySQL rows: 3',result['result']['output'])
        self.service.call({'op':'state','value':{'theme':'matcha','draft':'SELECT 1'}})
        self.assertEqual(self.service.call({'op':'state'})['value']['theme'],'matcha')
        for name in ['../../tmp/escape.py','/etc/passwd','.hidden.sql']:
            with self.assertRaises(DeskError): self.service.call({'op':'save','name':name,'text':'test'})
        with self.assertRaises(DeskError):
            self.service.call({'op':'save','name':'api-check.py','text':'overwrite','expectedText':'outdated'})

    def test_05_cancel_stops_real_query_and_rejects_overlap(self):
        run=self.service.start({'op':'execute','sql':'SELECT SLEEP(15)'})
        with self.assertRaises(DeskError): self.service.start({'op':'execute','sql':'SELECT 1'})
        time.sleep(.5)
        started=time.monotonic();self.service.cancel(run['id']);result=self.wait(run['id'])
        self.assertEqual(result['state'],'cancelled')
        self.assertLess(time.monotonic()-started,8)
        self.assertEqual(self.sql('SELECT 2')['state'],'done')

    def test_06_row_preview_limit_and_pagination(self):
        self.sql('DROP TABLE IF EXISTS desk_many; CREATE TABLE desk_many (id INT PRIMARY KEY); INSERT INTO desk_many WITH RECURSIVE n AS (SELECT 1 AS x UNION ALL SELECT x+1 FROM n WHERE x<650) SELECT x FROM n;')
        result=self.sql('SELECT id FROM desk_many ORDER BY id')['result']['results'][0]
        self.assertEqual(len(result['rows']),500)
        self.assertEqual(result['rowCount'],650)
        self.assertTrue(result['truncated'])
        page=self.service.call({'op':'table','table':'desk_many','offset':100,'limit':100})
        self.assertEqual(page['rows'][0][0],101)
        self.assertEqual(page['total'],650)


if __name__=='__main__': unittest.main()
