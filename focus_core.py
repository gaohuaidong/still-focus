"""Offline timer and atomic local storage; no GUI or network dependencies."""
from datetime import datetime, time as day_time, timedelta
import copy
import json
import math
import os
from pathlib import Path

DEFAULTS = {'focus': 25, 'short': 5, 'long': 15, 'cycle': 4, 'goal': 4, 'sound': True}
MODES = ('focus', 'short', 'long')


def day_key(stamp):
    return datetime.fromtimestamp(stamp).strftime('%Y-%m-%d')


def add_time(parts, start, end):
    """Split elapsed time at local midnight, including local DST boundaries."""
    while start < end:
        local = datetime.fromtimestamp(start)
        midnight = datetime.combine(local.date() + timedelta(days=1), day_time()).timestamp()
        stop = min(end, midnight)
        if stop <= start:
            break
        key = day_key(start)
        parts[key] = parts.get(key, 0.0) + stop - start
        start = stop


def valid_number(value, lower, upper):
    return type(value) in (int, float) and math.isfinite(value) and lower <= value <= upper


class Timer:
    def __init__(self, settings=None):
        self.settings = dict(DEFAULTS)
        self.settings.update(settings or {})
        self.mode = 'focus'
        self.remaining = self.settings['focus'] * 60.0
        self.running = False
        self.task = ''
        self.parts = {}
        self.started = None
        self.last_mono = None
        self.completed_focus = 0
        self.duration = self.remaining
        self.notice = ''

    def start(self, mono, wall):
        if not self.running:
            self.running = True
            self.last_mono = mono
            self.started = self.started if self.started is not None else wall
            self.notice = ''

    def tick(self, mono, wall):
        if not self.running:
            return None
        delta = mono - self.last_mono
        self.last_mono = mono
        if delta < 0 or delta > 5:
            self.running = False
            self.notice = '检测到休眠或计时中断，已暂停。'
            return None
        used = min(delta, self.remaining)
        if self.mode == 'focus':
            add_time(self.parts, wall - delta, wall - delta + used)
        self.remaining = max(0.0, self.remaining - used)
        if self.remaining > 0:
            return None
        self.running = False
        record = self.record(wall - delta + used, 'completed')
        old_mode = self.mode
        if old_mode == 'focus':
            self.completed_focus += 1
            self.select('long' if self.completed_focus % self.settings['cycle'] == 0 else 'short')
        else:
            self.select('focus')
        return record

    def record(self, wall, status):
        return {'mode': self.mode, 'task': self.task.strip() or '自由专注',
                'started': self.started, 'ended': wall, 'status': status,
                'duration': self.duration, 'elapsed': max(0, self.duration - self.remaining),
                'parts': dict(self.parts)}

    def select(self, mode):
        if mode not in MODES:
            raise ValueError('Unknown timer mode')
        self.mode = mode
        self.duration = self.settings[mode] * 60.0
        self.remaining = self.duration
        self.running = False
        self.parts = {}
        self.started = None
        self.last_mono = None
        self.notice = ''

    def snapshot(self):
        return {key: copy.deepcopy(getattr(self, key)) for key in
                ('mode', 'remaining', 'duration', 'task', 'parts', 'started', 'completed_focus')}

    def restore(self, data):
        if not isinstance(data, dict):
            return
        mode = data.get('mode', 'focus')
        duration = data.get('duration')
        remaining = data.get('remaining')
        if mode not in MODES or not valid_number(duration, 60, 10800) or not valid_number(remaining, 0.01, duration):
            return
        self.mode, self.duration, self.remaining = mode, float(duration), float(remaining)
        self.task = str(data.get('task', ''))[:100]
        self.parts = {k: float(v) for k, v in data.get('parts', {}).items()
                      if isinstance(k, str) and valid_number(v, 0, 10800)} if isinstance(data.get('parts'), dict) else {}
        started = data.get('started')
        self.started = started if valid_number(started, 0, 100_000_000_000) else None
        count = data.get('completed_focus', 0)
        self.completed_focus = count if type(count) is int and count >= 0 else 0
        self.running = False


class Store:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.path = self.directory / 'focus.json'
        self.settings = dict(DEFAULTS)
        self.records = []
        self.active = {}
        self.warning = ''
        try:
            data = json.loads(self.path.read_text(encoding='utf-8'))
            if not isinstance(data, dict):
                raise ValueError('Invalid data')
            for key, value in data.get('settings', {}).items():
                if key == 'sound' and type(value) is bool:
                    self.settings[key] = value
                elif key in MODES and type(value) is int and 1 <= value <= 180:
                    self.settings[key] = value
                elif key in ('cycle', 'goal') and type(value) is int and 1 <= value <= 12:
                    self.settings[key] = value
            self.records = [r for r in data.get('records', []) if isinstance(r, dict)
                            and r.get('mode') in MODES and isinstance(r.get('parts'), dict)
                            and valid_number(r.get('ended'), 0, 100_000_000_000)
                            and valid_number(r.get('elapsed'), 0, 10800)
                            and all(isinstance(k, str) and valid_number(v, 0, 10800)
                                    for k, v in r['parts'].items())]
            self.active = data.get('active', {})
        except FileNotFoundError:
            pass
        except (ValueError, TypeError, AttributeError):
            # Never overwrite an unreadable personal history with an empty one.
            self.warning = '记录文件格式损坏；已保留原文件。本次不会覆盖保存，请先备份并移走该文件。'
        except OSError:
            self.warning = '无法读取记录目录。本次不会覆盖保存，请检查目录权限。'

    def save(self, timer):
        if self.warning:
            raise OSError(self.warning)
        self.directory.mkdir(parents=True, exist_ok=True)
        data = {'version': 1, 'settings': self.settings, 'records': self.records, 'active': timer.snapshot()}
        temp = self.path.with_suffix('.tmp')
        with temp.open('w', encoding='utf-8') as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, self.path)

    def seconds(self, day, timer):
        total = sum(r['parts'].get(day, 0) for r in self.records if r['mode'] == 'focus')
        return total + timer.parts.get(day, 0)

    def completed(self, day):
        return sum(r['mode'] == 'focus' and r.get('status') == 'completed' and day_key(r['ended']) == day
                   for r in self.records)
