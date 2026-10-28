"""Isolated regression tests for project-wide fixes; no device connections."""
import os,sys,tempfile,unittest,io,csv
from unittest.mock import patch
os.environ['NIP_DATA_DIR']=tempfile.mkdtemp(prefix='linscope-project-audit-')
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]) if '__file__' in globals() else '/app/backend')
from app import service
from app.collect import runner,importer
from app.store import get_store
from app.device_fields import normalize_management_ip
from app.routers import reports

class ProjectRegressions(unittest.TestCase):
    def test_overview_pending_and_history(self):
        store=get_store();store.device_upsert({'ip':'192.0.2.101','role':'核心交换机','vendor':'huawei','pending_collection':True})
        run=store.collect_run_start('manual','regression-test');store.collect_run_finish(run,1,0,1,0,1,'test')
        data=runner.overview(pending_only=True)
        self.assertTrue(any(d['ip']=='192.0.2.101' for d in data['devices']))
        self.assertTrue(data['runs']);self.assertGreaterEqual(data['stats']['7d']['runs'],1)
    def test_device_identity_collision(self):
        device={'id':11,'ip':'192.0.2.11','name':'current','kind':'switch','group_kind':'switch','health_reasons':[]}
        wrong={'device_id':11,'device_ip':'192.0.2.22','inspected_at':'2099-01-01','cpu':99}
        own={'device_id':99,'device_ip':'192.0.2.11','inspected_at':'2026-01-01','cpu':7}
        legacy={'device_id':11,'inspected_at':'2025-01-01','cpu':5}
        with patch.object(service,'devices_view',return_value=([device],'local',{})),patch.object(service,'fetch',side_effect=lambda kind,**kw:([wrong,own,legacy] if kind=='inspections' else [],'local',{})):
            detail=service.device_detail('192.0.2.11')
        self.assertEqual([r['cpu'] for r in detail['inspections']],[7,5])
    def test_ip_and_csv_validation(self):
        self.assertEqual(normalize_management_ip(' 2001:0db8::1 '),'2001:db8::1')
        for invalid in ['not-an-ip','256.1.1.1','', '127.0.0.1; reboot']:
            with self.assertRaises(ValueError):normalize_management_ip(invalid)
        for text in ['', '序列号,设备角色\nA,交换机', '序列号,设备角色,IP地址,设备地点\nA,交换机,not-an-ip,R01']:
            self.assertEqual(importer.import_devices_csv(text,dry_run=True)['error_count'],1)
        csv_text='序列号,设备角色,IP地址,设备地点\n00001,应用服务器,192.0.2.150,R01'
        before=len(get_store().devices());pre=importer.import_devices_csv(csv_text,True);self.assertEqual(pre['error_count'],0);self.assertEqual(len(get_store().devices()),before)
        result=importer.import_devices_csv(csv_text);self.assertEqual(result['created'],1);self.assertEqual(get_store().device_get('192.0.2.150')['serial'],'00001');self.assertEqual(get_store().ledger_get('192.0.2.150')['location'],'R01')
    def test_invalid_health_key_keeps_pool(self):
        pool=[{'id':1,'ip':'192.0.2.1','name':'valid','group_kind':'server'}]
        with patch.object(service,'devices_view',return_value=(pool,'local',{})):
            result=service.health_page('server','not-a-device')
        self.assertIsNone(result['device']);self.assertEqual(result['pool'],pool)
    def test_archive_missing_operator(self):
        fake={'exports':[{'id':1,'filename':'health.pdf','kind':'server','fmt':'pdf','operator':None,'params':{}}], 'templates':[], 'formats':[]}
        with patch.object(service,'report_archive',return_value=fake):
            result=reports.archive(keyword='health',page=1,page_size=20)
        self.assertEqual(result['total'],1)

unittest.main(testRunner=unittest.TextTestRunner(stream=sys.stdout,verbosity=2))
