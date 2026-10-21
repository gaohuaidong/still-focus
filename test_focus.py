from datetime import datetime
import json
from pathlib import Path
import tempfile
import unittest

from focus_core import Timer, Store, add_time, day_key


class TimerTests(unittest.TestCase):
    def test_pause_resume_does_not_count_idle(self):
        timer=Timer()
        timer.start(0,1700001000)
        timer.tick(2,1700001002)
        timer.running=False
        timer.tick(200,1700001200)
        timer.start(201,1700001201)
        timer.tick(203,1700001203)
        self.assertAlmostEqual(timer.remaining,1496)
        self.assertAlmostEqual(sum(timer.parts.values()),4)

    def test_sleep_pauses_without_credit(self):
        timer=Timer()
        timer.start(10,1700001000)
        timer.tick(12,1700001002)
        timer.tick(112,1700001102)
        self.assertFalse(timer.running)
        self.assertEqual(timer.remaining,1498)
        self.assertEqual(sum(timer.parts.values()),2)
        self.assertTrue(timer.notice)

    def test_completion_credits_only_duration_once_and_selects_rest(self):
        timer=Timer({'focus':1})
        timer.start(0,1700001000)
        record=None
        for step in range(1,22):
            found=timer.tick(step*3,1700001000+step*3)
            if found:
                record=found
        self.assertEqual(record['status'],'completed')
        self.assertEqual(record['elapsed'],60)
        self.assertEqual(sum(record['parts'].values()),60)
        self.assertEqual(record['ended'],1700001060)
        self.assertEqual(timer.mode,'short')
        self.assertFalse(timer.running)
        self.assertIsNone(timer.tick(100,1700001100))

    def test_long_rest_on_fourth_focus_and_no_credit_for_rest(self):
        timer=Timer({'focus':1,'short':1})
        timer.completed_focus=3
        timer.start(0,1700001000)
        for i in range(1,61):
            record=timer.tick(i,1700001000+i)
        self.assertEqual(timer.mode,'long')
        self.assertEqual(timer.completed_focus,4)
        timer.select('short')
        timer.start(0,1700002000)
        for i in range(1,61):
            record=timer.tick(i,1700002000+i)
        self.assertEqual(record['parts'],{})
        self.assertEqual(timer.mode,'focus')

    def test_midnight_split(self):
        start=datetime(2026,10,20,23,59,58).timestamp()
        parts={}
        add_time(parts,start,start+4)
        self.assertEqual(parts,{'2026-10-20':2,'2026-10-21':2})

    def test_restart_restores_progress_but_never_running(self):
        first=Timer()
        first.task='合成测试任务'
        first.start(0,1700001000)
        first.tick(3,1700001003)
        second=Timer()
        second.restore(first.snapshot())
        self.assertFalse(second.running)
        self.assertEqual(second.remaining,1497)
        self.assertEqual(sum(second.parts.values()),3)
        self.assertEqual(second.task,first.task)

    def test_invalid_restore_is_ignored(self):
        timer=Timer()
        timer.restore({'mode':'focus','duration':1500,'remaining':float('nan')})
        self.assertEqual(timer.remaining,1500)
        timer.restore({'mode':'other','duration':100,'remaining':50})
        self.assertEqual(timer.mode,'focus')


class StoreTests(unittest.TestCase):
    def test_roundtrip_and_no_double_count_when_session_ends(self):
        with tempfile.TemporaryDirectory() as folder:
            store=Store(folder)
            timer=Timer()
            timer.start(0,1700001000)
            timer.tick(3,1700001003)
            today=day_key(1700001003)
            self.assertEqual(store.seconds(today,timer),3)
            store.records.append(timer.record(1700001003,'interrupted'))
            timer.select('short')
            self.assertEqual(store.seconds(today,timer),3)
            store.save(timer)
            loaded=Store(folder)
            self.assertEqual(loaded.records,store.records)
            self.assertEqual(loaded.active['mode'],'short')

    def test_bad_json_is_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'focus.json'
            path.write_text('broken',encoding='utf8')
            store=Store(folder)
            self.assertTrue(store.warning)
            with self.assertRaises(OSError):
                store.save(Timer())
            self.assertEqual(path.read_text(),'broken')

    def test_bad_settings_and_record_values_are_not_imported(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'focus.json'
            path.write_text(json.dumps({'settings':{'focus':-1,'short':999,'sound':'yes'},'records':[{'mode':'focus','parts':{'x':'bad'},'ended':100,'elapsed':2}]}))
            store=Store(folder)
            self.assertEqual(store.settings['focus'],25)
            self.assertTrue(store.settings['sound'])
            self.assertEqual(store.records,[])


if __name__=='__main__':
    unittest.main()
