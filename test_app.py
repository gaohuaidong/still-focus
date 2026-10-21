"""Exercise our own UI callbacks with isolated synthetic storage."""
from pathlib import Path
import tempfile
import time
import tkinter as tk
import unittest
from unittest.mock import patch

from app import App
from focus_core import day_key


class AppTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=tk.Tk()
        self.root.withdraw()
        self.app=App(self.root,Path(self.temp.name))
        self.app.store.settings['sound']=False

    def tearDown(self):
        for job in self.root.tk.call('after','info'):
            self.root.after_cancel(job)
        self.root.destroy()
        self.temp.cleanup()

    def test_completion_reminder_and_restart_without_duplicate_credit(self):
        app=self.app
        now=time.time()
        app.task.set('合成任务')
        app.timer.duration=60
        app.timer.remaining=.1
        app.timer.parts={day_key(now):59.9}
        app.timer.started=now-59.9
        app.timer.running=True
        app.timer.last_mono=time.monotonic()-.2
        app.tick()
        self.assertEqual(len(app.store.records),1)
        self.assertIsNotNone(app.popup)
        self.assertEqual(app.timer.mode,'short')
        self.assertFalse(app.timer.running)
        self.assertAlmostEqual(app.store.seconds(day_key(now),app.timer),60,places=4)
        app.tick()
        self.assertEqual(len(app.store.records),1)
        self.assertEqual(app.store.records[0]['task'],'合成任务')

    def test_early_finish_saves_elapsed_and_switches_mode(self):
        app=self.app
        now=time.time()
        app.timer.started=now-10
        app.timer.remaining=1490
        app.timer.parts={day_key(now):10}
        app.finish_early('short')
        self.assertEqual(len(app.store.records),1)
        self.assertEqual(app.store.records[0]['status'],'interrupted')
        self.assertEqual(app.store.seconds(day_key(now),app.timer),10)
        self.assertEqual(app.timer.mode,'short')

    def test_close_and_reopen_keeps_paused_progress(self):
        app=self.app
        app.task.set('测试恢复')
        app.toggle()
        app.timer.last_mono=time.monotonic()-1
        app.settle()
        app.timer.running=False
        self.assertTrue(app.save())
        other_root=tk.Toplevel(self.root)
        # Toplevel supports the same app window methods used here.
        other=App(other_root,Path(self.temp.name))
        self.assertFalse(other.timer.running)
        self.assertLess(other.timer.remaining,1500)
        self.assertEqual(other.timer.task,'测试恢复')
        other_root.destroy()

    def test_compact_and_mini_switch_preserve_active_timer(self):
        app=self.app
        self.root.deiconify()
        self.root.update()
        app.task.set('切换窗口测试')
        app.toggle()
        app.timer.last_mono=time.monotonic()-1
        app.settle()
        remaining=app.timer.remaining
        app.navigate('mini')
        self.root.update()
        self.assertEqual((self.root.winfo_width(),self.root.winfo_height()),(320,176))
        self.assertTrue(app.timer.running)
        self.assertAlmostEqual(app.timer.remaining,remaining,places=1)
        self.assertTrue(app.pinned)
        app.toggle_pin()
        self.assertFalse(app.pinned)
        app.navigate('timer')
        self.root.update()
        self.assertEqual((self.root.winfo_width(),self.root.winfo_height()),(420,540))
        self.assertEqual(app.timer.task,'切换窗口测试')
        self.assertTrue(app.timer.running)

    def test_history_paginates_all_sessions(self):
        app=self.app
        now=time.time()
        day=day_key(now)
        for i in range(9):
            app.store.records.append({'mode':'focus','task':f'测试片段{i}',
                'ended':now-i,'status':'completed','parts':{day:60},'elapsed':60})
        self.root.deiconify()
        self.root.update()
        app.navigate('history')
        self.root.update()
        self.assertEqual(len(app.day_records()),9)
        app.history_page(1)
        self.assertEqual(app.history_offset,4)
        app.history_page(1)
        self.assertEqual(app.history_offset,8)
        app.history_page(1)
        self.assertEqual(app.history_offset,8)
        app.history_move(-1)
        self.assertEqual(app.history_offset,0)
        self.assertEqual(app.day_records(),[])


if __name__=='__main__':
    unittest.main()
