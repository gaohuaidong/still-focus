"""留白 · Focus — a small offline Windows focus companion."""
import ctypes
from datetime import datetime, timedelta
import math
import os
from pathlib import Path
import sys
import time
import tkinter as tk
from tkinter import ttk, messagebox

from focus_core import Store, Timer, day_key

BG = '#F7F8F5'
WHITE = '#FFFFFF'
INK = '#263D34'
MUTED = '#6D7B73'
GREEN = '#32654E'
PALE = '#E5EEE5'
LINE = '#E6E9E1'
AMBER = '#B77945'
FONT = 'Microsoft YaHei UI'
TITLES = {'focus': '专注', 'short': '短休息', 'long': '长休息'}


def data_directory():
    return Path(os.environ.get('STILLFOCUS_DATA_DIR') or Path(os.environ.get('LOCALAPPDATA', Path.home())) / 'StillFocus')


class App:
    def __init__(self, root, directory=None):
        self.root = root
        self.store = Store(directory or data_directory())
        self.timer = Timer(self.store.settings)
        self.timer.restore(self.store.active)
        self.root.title('留白 · Focus')
        self.root.geometry('420x540')
        self.root.minsize(380, 530)
        self.root.configure(bg=BG)
        icon = Path(getattr(sys, '_MEIPASS', Path(__file__).parent)) / 'assets' / 'focus.ico'
        if icon.exists():
            self.root.iconbitmap(str(icon))
        self.canvas = tk.Canvas(root, bg=BG, highlightthickness=0)
        self.canvas.pack(fill='both', expand=True)
        self.task = tk.StringVar(value=self.timer.task)
        self.task.trace_add('write', self.task_changed)
        self.entry = tk.Entry(self.canvas, textvariable=self.task, bg=WHITE, fg=INK,
                              insertbackground=GREEN, bd=0, justify='center', font=(FONT, 12),
                              selectbackground=PALE, relief='flat')
        self.entry.bind('<FocusIn>', self.entry_focus)
        self.entry.bind('<FocusOut>', self.entry_blur)
        self.entry.bind('<Return>', lambda event: self.canvas.focus_set())
        self.regions = []
        self.page = 'timer'
        self.pinned = False
        self.timer_size = (420, 540)
        self.history_offset = 0
        self.history_signature = None
        self.chart_signature = None
        self.history_day = day_key(time.time())
        self.last_save = time.monotonic()
        self.last_day = day_key(time.time())
        self.save_error = ''
        self.popup = None
        self.resize_job = None
        self.closed = False
        self.ids = {}
        self.canvas.bind('<Button-1>', self.click)
        self.canvas.bind('<Motion>', self.hover)
        self.canvas.bind('<Configure>', self.resize)
        self.root.bind('<space>', self.keyboard)
        self.root.bind('<Control-m>', lambda event: self.navigate('timer' if self.page == 'mini' else 'mini'))
        self.root.bind('<Control-h>', lambda event: self.navigate('history'))
        self.root.bind('<Escape>', self.escape)
        self.root.protocol('WM_DELETE_WINDOW', self.close)
        self.root.bind('<Destroy>', self.on_destroy, add='+')
        self.initial_draw_job = self.root.after(80, self.draw)
        self.tick_job = self.root.after(200, self.tick)
        if self.store.warning:
            self.root.after(300, lambda: messagebox.showwarning('记录未加载', self.store.warning, parent=self.root))

    def text(self, x, y, value, size=11, color=INK, weight='normal', anchor='w', **kwargs):
        return self.canvas.create_text(x, y, text=value, fill=color, font=(FONT, size, weight),
                                       anchor=anchor, **kwargs)

    def box(self, x, y, w, h, fill=WHITE, radius=18, outline=''):
        r = min(radius, w / 2, h / 2)
        points = [x+r,y,x+w-r,y,x+w,y,x+w,y+r,x+w,y+h-r,x+w,y+h,
                  x+w-r,y+h,x+r,y+h,x,y+h,x,y+h-r,x,y+r,x,y]
        return self.canvas.create_polygon(points, smooth=True, splinesteps=24, fill=fill,
                                          outline=outline or fill, width=1)

    def button(self, x, y, w, h, label, callback, fill=PALE, color=GREEN, size=11):
        shape = self.box(x, y, w, h, fill, 12)
        text = self.text(x+w/2, y+h/2, label, size, color, 'bold', 'center')
        self.regions.append((x, y, x+w, y+h, callback))
        return shape, text

    def resize(self, event):
        if self.closed:
            return
        if self.resize_job:
            self.root.after_cancel(self.resize_job)
        self.resize_job = self.root.after(100, self.draw)

    def entry_focus(self, event=None):
        if self.entry.get() == '给这段专注起个名字…' and not self.timer.task:
            self.task.set('')
        self.entry.configure(fg=INK)

    def task_changed(self, *args):
        value = self.task.get()
        if value != '给这段专注起个名字…':
            self.timer.task = value.strip()[:100]

    def entry_blur(self, event=None):
        value = self.entry.get().strip()
        if value == '给这段专注起个名字…':
            value = ''
        self.timer.task = value[:100]
        self.task.set(value or '给这段专注起个名字…')
        self.entry.configure(fg=INK if value else MUTED)

    def click(self, event):
        self.canvas.focus_set()
        for x1, y1, x2, y2, callback in reversed(self.regions):
            if x1 <= event.x <= x2 and y1 <= event.y <= y2:
                callback()
                return

    def hover(self, event):
        self.canvas.configure(cursor='hand2' if any(x1 <= event.x <= x2 and y1 <= event.y <= y2
                              for x1,y1,x2,y2,_ in self.regions) else '')

    def keyboard(self, event):
        if self.popup or isinstance(self.root.focus_get(), (tk.Entry, ttk.Entry, tk.Spinbox, ttk.Spinbox)):
            return
        self.toggle()
        return 'break'

    def escape(self, event=None):
        if not self.popup and self.page != 'timer':
            self.navigate('timer')

    def navigate(self, page):
        if self.popup or page == self.page:
            return
        self.entry_blur()
        if self.page == 'timer' and self.root.winfo_width() >= 380:
            self.timer_size = (self.root.winfo_width(), self.root.winfo_height())
        self.page = page
        self.root.resizable(page != 'mini', page != 'mini')
        if page == 'mini':
            width, height = 320, 176
            self.root.minsize(width, height)
            self.pinned = True
        elif page == 'history':
            width, height = 520, 660
            self.root.minsize(480, 620)
            self.pinned = False
            self.history_offset = 0
        else:
            width, height = self.timer_size
            self.root.minsize(380, 530)
            self.pinned = False
        self.root.attributes('-topmost', self.pinned)
        x = max(0, min(self.root.winfo_x(), self.root.winfo_screenwidth()-width-16))
        y = max(0, min(self.root.winfo_y(), self.root.winfo_screenheight()-height-60))
        self.root.geometry(f'{width}x{height}+{x}+{y}')
        self.draw()

    def toggle_pin(self):
        self.pinned = not self.pinned
        self.root.attributes('-topmost', self.pinned)
        self.draw()

    def draw(self):
        if self.closed:
            return
        if self.resize_job:
            self.root.after_cancel(self.resize_job)
        self.resize_job = None
        self.canvas.delete('all')
        self.regions = []
        self.ids = {}
        self.chart_signature = None
        self.week_geometry = None
        w, h = self.canvas.winfo_width(), self.canvas.winfo_height()
        if w < 280 or h < 140:
            return
        if self.page == 'mini':
            self.draw_mini(w, h)
        elif self.page == 'history':
            self.draw_history(w, h)
        else:
            self.canvas.create_oval(20, 13, 47, 40, fill=GREEN, outline='')
            self.canvas.create_line(33, 20, 33, 27, 39, 30, fill=WHITE, width=2, capstyle='round')
            self.text(57, 26, '留白', 14, weight='bold')
            self.button(w-168, 12, 46, 30, '迷你', lambda: self.navigate('mini'), BG, MUTED, 9)
            self.button(w-115, 12, 46, 30, '记录', lambda: self.navigate('history'), BG, MUTED, 9)
            self.button(w-62, 12, 46, 30, '设置', self.settings, BG, MUTED, 9)
            self.draw_timer(w, h)
        self.refresh()

    def draw_timer(self, w, h):
        cx = w/2
        self.box(16, 56, w-32, h-152, WHITE, 20)
        tabs_width = min(300, w-72)
        tab = tabs_width/3
        left = cx-tabs_width/2
        self.box(left, 73, tabs_width, 34, '#EFF2EC', 10)
        for index, mode in enumerate(TITLES):
            active = self.timer.mode == mode
            self.button(left+index*tab+3, 76, tab-6, 28, TITLES[mode],
                        lambda mode=mode: self.switch(mode),
                        WHITE if active else '#EFF2EC', GREEN if active else MUTED, 10)
        self.task.set(self.timer.task or '给这段专注起个名字…')
        self.entry.configure(fg=INK if self.timer.task else MUTED, font=(FONT, 10))
        self.canvas.create_window(cx, 140, window=self.entry, width=w-92, height=28)
        cy = 263 + (h-540)*0.32
        r = 91
        self.canvas.create_oval(cx-r,cy-r,cx+r,cy+r,outline='#EAF0E7',width=5)
        self.ids['arc'] = self.canvas.create_arc(cx-r,cy-r,cx+r,cy+r,start=90,extent=-0.5,
                                                style='arc',outline=GREEN,width=5,state='hidden')
        self.ids['time'] = self.canvas.create_text(cx,cy-4,text='',fill=INK,font=('Segoe UI',44,'bold'))
        self.ids['timer_note'] = self.text(cx,cy+41,'',9,MUTED,anchor='center')
        primary_y = h-160
        self.ids['primary_shape'],self.ids['primary_text'] = self.button(40,primary_y,w-142,44,'',self.toggle,GREEN,WHITE,11)
        self.button(w-90,primary_y,50,44,'↺',self.reset,'#EFF3EC',GREEN,18)
        self.box(16,h-83,w-32,57,'#E9EFE5',13)
        self.text(32,h-65,'今日',9,MUTED)
        self.ids['summary'] = self.text(32,h-43,'',10,INK,'bold')
        self.ids['goal_geometry'] = (w-116,h-51,84)
        self.ids['notice'] = self.text(w/2,h-12,'',8,MUTED,anchor='center',width=w-36)

    def draw_mini(self, w, h):
        self.box(1,1,w-2,h-2,WHITE,12)
        self.ids['mini_mode'] = self.text(18,23,TITLES[self.timer.mode],10,GREEN,'bold')
        self.button(w-112,8,46,28,'已置顶' if self.pinned else '置顶',self.toggle_pin,
                    PALE if self.pinned else WHITE,GREEN if self.pinned else MUTED,8)
        self.button(w-59,8,44,28,'展开',lambda:self.navigate('timer'),WHITE,MUTED,9)
        self.ids['time'] = self.canvas.create_text(18,78,text='',fill=INK,font=('Segoe UI',38,'bold'),anchor='w')
        self.ids['primary_shape'],self.ids['primary_text'] = self.button(w-92,53,74,44,'',self.toggle,GREEN,WHITE,10)
        self.ids['timer_note'] = self.text(19,121,'',9,MUTED)
        self.box(18,h-27,w-36,4,'#E7EDE3',2)
        self.ids['mini_bar_geometry'] = (18,h-27,w-36)
        self.ids['notice'] = self.text(19,h-10,'',7,AMBER)

    def day_records(self):
        return [r for r in reversed(self.store.records) if r['mode']=='focus' and self.history_day in r['parts']]

    def draw_history(self, w, h):
        day = self.history_day
        self.button(16,12,64,32,'‹  返回',lambda:self.navigate('timer'),BG,GREEN,10)
        self.text(w/2,28,'专注记录',14,weight='bold',anchor='center')
        self.button(w-68,12,52,32,'今天',lambda:self.history_select(day_key(time.time())),BG,GREEN,9)
        self.button(19,65,32,30,'‹',lambda:self.history_move(-1),PALE,GREEN,15)
        self.text(w/2,80,day+'  ·  '+('今天' if day==day_key(time.time()) else '每日记录'),11,anchor='center')
        self.button(w-51,65,32,30,'›',lambda:self.history_move(1),PALE,GREEN,15)
        self.box(16,110,w-32,78,WHITE,14)
        self.text(32,132,'专注分钟',9,MUTED)
        self.ids['history_minutes'] = self.text(32,163,'',23,weight='bold')
        self.text(w/2+8,132,'完成 / 每日目标',9,MUTED)
        self.text(w/2+8,163,f'{self.store.completed(day)} / {self.store.settings["goal"]}',23,weight='bold')
        self.draw_week(16,201,w-32,163)
        self.box(16,377,w-32,h-401,WHITE,14)
        self.text(32,400,'专注片段',11,weight='bold')
        records = self.day_records()
        pages = max(1, math.ceil(len(records)/4))
        self.history_offset = min(self.history_offset,(pages-1)*4)
        page = self.history_offset//4+1
        self.text(w-104,400,f'{page} / {pages}',9,MUTED,anchor='e')
        self.button(w-93,387,30,26,'‹',lambda:self.history_page(-1),BG,MUTED,12)
        self.button(w-58,387,30,26,'›',lambda:self.history_page(1),BG,MUTED,12)
        if not records:
            self.text(w/2,468,'这一天还没有结束的专注',11,MUTED,anchor='center')
            self.text(w/2,495,'完成或提前结束后，片段会出现在这里。',9,MUTED,anchor='center')
        for i,record in enumerate(records[self.history_offset:self.history_offset+4]):
            yy = 438+i*44
            task = str(record.get('task','自由专注'))
            self.text(32,yy,task[:22]+('…' if len(task)>22 else ''),10)
            self.text(w-32,yy,f'{record["parts"].get(day,0)/60:.1f} 分钟',10,GREEN,anchor='e')
            status = '完成' if record.get('status')=='completed' else '提前结束'
            self.text(32,yy+17,datetime.fromtimestamp(record['ended']).strftime('%H:%M')+' · '+status,8,MUTED)
        self.ids['notice'] = self.text(w/2,h-11,'按本机日期统计 · 点击柱形切换日期',8,MUTED,anchor='center')
        self.history_signature = (day,len(self.store.records))

    def draw_week(self, x, y, width, height):
        self.box(x,y,width,height,WHITE,14)
        self.text(x+16,y+22,'最近七天',10,weight='bold')
        self.text(x+width-16,y+22,'分钟',8,MUTED,anchor='e')
        self.week_geometry = (x,y,width,height)
        today = datetime.now().date()
        for i in range(7):
            date = (today-timedelta(days=6-i)).isoformat()
            px = x+32+i*(width-64)/6
            self.regions.append((px-20,y+40,px+20,y+height-8,lambda date=date:self.history_select(date)))
        self.paint_week()

    def paint_week(self):
        if not self.week_geometry:
            return
        x,y,width,height = self.week_geometry
        today = datetime.now().date()
        days = [today-timedelta(days=i) for i in range(6,-1,-1)]
        values = [self.store.seconds(d.isoformat(),self.timer)/60 for d in days]
        signature = (today,self.history_day,tuple(int(v*10) for v in values))
        if signature == self.chart_signature:
            return
        self.chart_signature = signature
        self.canvas.delete('weekly')
        ceiling = max(30,max(values))
        base = y+height-33
        for i,(day,value) in enumerate(zip(days,values)):
            px = x+32+i*(width-64)/6
            bar_h = max(3,value/ceiling*65)
            color = GREEN if day.isoformat()==self.history_day else '#CADCC5'
            self.canvas.create_rectangle(px-10,base-bar_h,px+10,base,fill=color,outline='',tags='weekly')
            self.text(px,base+16,'今' if i==6 else str(day.day),8,MUTED,anchor='center',tags='weekly')
            if value>=1:
                self.text(px,base-bar_h-10,str(int(value)),8,MUTED,anchor='center',tags='weekly')

    def history_select(self, date):
        self.history_day = date
        self.history_offset = 0
        self.draw()

    def history_move(self, days):
        date = datetime.strptime(self.history_day,'%Y-%m-%d').date()+timedelta(days=days)
        if date<=datetime.now().date():
            self.history_select(date.isoformat())

    def history_page(self, step):
        last = max(0,(math.ceil(len(self.day_records())/4)-1)*4)
        self.history_offset = max(0,min(last,self.history_offset+step*4))
        self.draw()

    def refresh(self):
        if self.page == 'history' and 'history_minutes' in self.ids:
            if self.history_signature != (self.history_day,len(self.store.records)):
                self.draw()
                return
            self.canvas.itemconfigure(self.ids['history_minutes'],text=f'{self.store.seconds(self.history_day,self.timer)/60:.1f}')
            self.paint_week()
            self.canvas.itemconfigure(self.ids['notice'],text=self.save_error or '按本机日期统计 · 点击柱形切换日期',fill=AMBER if self.save_error else MUTED)
            return
        if 'time' not in self.ids:
            return
        seconds = math.ceil(self.timer.remaining)
        self.canvas.itemconfigure(self.ids['time'],text=f'{seconds//60:02d}:{seconds%60:02d}')
        elapsed = max(0,min(1,1-self.timer.remaining/self.timer.duration))
        color = GREEN if self.timer.mode=='focus' else AMBER
        state = '正在'+TITLES[self.timer.mode] if self.timer.running else ('已暂停' if elapsed>0 else '准备开始')
        label = 'Ⅱ  暂停' if self.timer.running else ('▶  继续' if elapsed>0 else '▶  开始')
        self.canvas.itemconfigure(self.ids['primary_text'],text=label)
        if self.page == 'mini':
            self.canvas.itemconfigure(self.ids['mini_mode'],text=TITLES[self.timer.mode],fill=color)
            task = self.timer.task or state
            self.canvas.itemconfigure(self.ids['timer_note'],text=task[:26]+('…' if len(task)>26 else ''))
            self.canvas.delete('mini-progress')
            bx,by,bw = self.ids['mini_bar_geometry']
            if elapsed>0:
                self.canvas.create_rectangle(bx,by,bx+bw*elapsed,by+4,fill=color,outline='',tags='mini-progress')
            self.canvas.itemconfigure(self.ids['notice'],text='保存失败，请展开查看' if self.save_error else ('计时已暂停，请展开查看' if self.timer.notice else ''))
            return
        self.canvas.itemconfigure(self.ids['arc'],extent=-max(0.5,min(359.5,elapsed*360)),
                                  state='normal' if elapsed>0.0001 else 'hidden',outline=color)
        cycle = self.store.settings['cycle']
        round_number = self.timer.completed_focus%cycle+1
        note = f'第 {round_number} / {cycle} 轮 · {state}' if self.timer.mode=='focus' else state
        self.canvas.itemconfigure(self.ids['timer_note'],text=note)
        today = day_key(time.time())
        count = self.store.completed(today)
        goal = self.store.settings['goal']
        self.canvas.itemconfigure(self.ids['summary'],text=f'{self.store.seconds(today,self.timer)/60:.1f} 分钟   ·   {count}/{goal} 次')
        self.canvas.delete('goal-dots')
        gx,gy,gw = self.ids['goal_geometry']
        for i in range(goal):
            diameter = min(8,gw/goal-2)
            px = gx+i*gw/goal
            self.canvas.create_oval(px,gy,px+diameter,gy+diameter,
                                    fill=GREEN if i<count else '#C8D8C1',outline='',tags='goal-dots')
        self.canvas.itemconfigure(self.ids['notice'],text=self.save_error or self.timer.notice or '空格暂停 / 继续  ·  Ctrl+M 迷你模式',fill=AMBER if self.save_error else MUTED)


    def save(self):
        self.last_save=time.monotonic()
        try:
            self.store.save(self.timer)
            self.save_error=''
            self.last_save=time.monotonic()
            return True
        except OSError:
            self.save_error='记录暂未保存，请检查数据目录权限与可用空间。'
            return False

    def settle(self):
        self.entry_blur()
        record=self.timer.tick(time.monotonic(),time.time())
        if record:
            self.store.records.append(record)
        return record

    def toggle(self):
        if self.popup:
            return
        record=self.settle()
        if record:
            self.save()
            self.draw()
            self.remind(record)
            return
        if self.timer.running:
            self.timer.running=False
        else:
            self.timer.start(time.monotonic(),time.time())
        self.save()
        self.refresh()

    def finish_early(self, mode):
        record=self.settle()
        if not record and self.timer.started is not None and self.timer.duration-self.timer.remaining>0.1:
            self.store.records.append(self.timer.record(time.time(),'interrupted'))
        self.timer.select(mode)
        self.save()
        self.draw()

    def switch(self, mode):
        if mode==self.timer.mode:
            return
        if self.timer.started is not None and not messagebox.askyesno('切换计时', '结束当前片段并切换？已专注时间会保留。',parent=self.root):
            return
        self.finish_early(mode)

    def reset(self):
        if self.timer.started is not None and not messagebox.askyesno('重新开始', '结束当前片段并重新计时？已专注时间会保留。',parent=self.root):
            return
        self.finish_early(self.timer.mode)

    def tick(self):
        if self.closed:
            return
        if self.tick_job:
            self.root.after_cancel(self.tick_job)
            self.tick_job = None
        record=self.timer.tick(time.monotonic(),time.time())
        if record:
            self.store.records.append(record)
            self.save()
            self.draw()
            self.remind(record)
        if day_key(time.time())!=self.last_day:
            self.last_day=day_key(time.time())
            self.draw()
        if time.monotonic()-self.last_save>=10:
            self.entry_blur() if self.root.focus_get() is not self.entry else None
            self.save()
        self.refresh()
        self.tick_job = self.root.after(200,self.tick)

    def on_destroy(self, event):
        if event.widget is not self.root:
            return
        self.closed = True
        for job in (self.initial_draw_job, self.tick_job, self.resize_job):
            if job:
                try:
                    self.root.after_cancel(job)
                except tk.TclError:
                    pass

    def remind(self, record):
        if self.store.settings['sound']:
            try:
                import winsound
                winsound.MessageBeep(winsound.MB_ICONASTERISK)
            except (ImportError,RuntimeError):
                self.root.bell()
        if self.popup:
            self.popup.destroy()
        win=tk.Toplevel(self.root)
        self.popup=win
        win.title('一段专注，告一段落')
        win.configure(bg=BG)
        win.resizable(False,False)
        win.attributes('-topmost',True)
        self.center(win,360,218)
        title='做得很好，休息一下。' if record['mode']=='focus' else '休息好了，慢慢回来。'
        tk.Label(win,text=title,bg=BG,fg=INK,font=(FONT,15,'bold')).pack(pady=(24,12))
        tk.Label(win,text=f'接下来：{TITLES[self.timer.mode]} {self.timer.duration/60:g} 分钟\n准备好后再开始。',bg=BG,fg=MUTED,font=(FONT,11),justify='center').pack()
        def dismiss(start=False):
            win.destroy()
            self.popup=None
            if start:
                self.toggle()
        tk.Button(win,text='开始'+TITLES[self.timer.mode],command=lambda:dismiss(True),bg=GREEN,fg=WHITE,
                  activebackground=GREEN,activeforeground=WHITE,bd=0,font=(FONT,11),padx=24,pady=10).pack(pady=18)
        win.protocol('WM_DELETE_WINDOW',dismiss)

    def center(self,win,width,height):
        self.root.update_idletasks()
        x=self.root.winfo_x()+(self.root.winfo_width()-width)//2
        y=self.root.winfo_y()+(self.root.winfo_height()-height)//2
        x=max(0,min(x,self.root.winfo_screenwidth()-width-16))
        y=max(0,min(y,self.root.winfo_screenheight()-height-60))
        win.geometry(f'{width}x{height}+{x}+{y}')

    def settings(self):
        if self.popup:
            self.popup.lift()
            return
        win=tk.Toplevel(self.root)
        self.popup=win
        win.title('偏好设置')
        win.configure(bg=BG)
        win.resizable(False,False)
        self.center(win,360,440)
        win.transient(self.root)
        win.grab_set()
        tk.Label(win,text='偏好设置',bg=BG,fg=INK,font=(FONT,15,'bold')).pack(anchor='w',padx=24,pady=(20,12))
        form=tk.Frame(win,bg=BG)
        form.pack(fill='x',padx=24)
        values={}
        for i,(key,label,limit) in enumerate([('focus','专注时长（分钟）',180),('short','短休息（分钟）',180),('long','长休息（分钟）',180),('cycle','几次专注后长休息',12),('goal','每日目标（完成次数）',12)]):
            tk.Label(form,text=label,bg=BG,fg=INK,font=(FONT,10)).grid(row=i,column=0,sticky='w',pady=7)
            var=tk.StringVar(value=str(self.store.settings[key]))
            values[key]=(var,limit)
            tk.Spinbox(form,from_=1,to=limit,textvariable=var,width=7,font=(FONT,11),bg=WHITE,fg=INK,
                       relief='flat',justify='center').grid(row=i,column=1,padx=(24,0))
        sound=tk.BooleanVar(value=self.store.settings['sound'])
        tk.Checkbutton(win,text='时间结束时播放提示音',variable=sound,bg=BG,fg=INK,activebackground=BG,
                       selectcolor=WHITE,font=(FONT,10)).pack(anchor='w',padx=19,pady=(10,8))
        tk.Label(win,text='时长更改从下一段计时生效。\n所有记录仅保存在这台电脑。',bg=BG,fg=MUTED,font=(FONT,9),justify='left').pack(anchor='w',padx=24)
        def dismiss():
            win.destroy()
            self.popup=None
        def apply():
            new={}
            try:
                for key,(var,limit) in values.items():
                    number=int(var.get())
                    if not 1<=number<=limit:
                        raise ValueError()
                    new[key]=number
            except ValueError:
                messagebox.showerror('请检查时长','时长应为 1–180 的整数，次数应为 1–12 的整数。',parent=win)
                return
            self.store.settings.update(new,sound=sound.get())
            self.timer.settings=dict(self.store.settings)
            if self.timer.started is None:
                self.timer.select(self.timer.mode)
            self.save()
            dismiss()
            self.draw()
        bottom=tk.Frame(win,bg=BG)
        bottom.pack(side='bottom',fill='x',padx=24,pady=20)
        tk.Button(bottom,text='数据文件夹',command=self.open_data,bd=0,bg=BG,fg=GREEN,font=(FONT,10)).pack(side='left')
        tk.Button(bottom,text='保存设置',command=apply,bd=0,bg=GREEN,fg=WHITE,padx=20,pady=9,font=(FONT,10)).pack(side='right')
        win.protocol('WM_DELETE_WINDOW',dismiss)

    def open_data(self):
        try:
            self.store.directory.mkdir(parents=True,exist_ok=True)
            os.startfile(str(self.store.directory))
        except OSError:
            messagebox.showerror('无法打开','请检查数据目录权限。',parent=self.popup or self.root)

    def close(self):
        self.settle()
        self.timer.running=False
        if not self.save() and not messagebox.askyesno('记录尚未保存','保存失败。仍然退出？本次未保存的进度可能丢失。',parent=self.root):
            return
        self.root.destroy()


def main():
    mutex=None
    if sys.platform=='win32':
        # Per-Windows-session and per-data-directory lock prevents parallel writers.
        import hashlib
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        kernel.CreateMutexW.argtypes=[ctypes.c_void_p,ctypes.c_int,ctypes.c_wchar_p]
        kernel.CreateMutexW.restype=ctypes.c_void_p
        digest=hashlib.sha256(str(data_directory().resolve()).lower().encode()).hexdigest()[:20]
        mutex=kernel.CreateMutexW(None,False,'Local\\StillFocus-'+digest)
        if not mutex:
            raise ctypes.WinError(ctypes.get_last_error())
        if ctypes.get_last_error()==183:
            ctypes.windll.user32.MessageBoxW(None,'留白已经在运行，请在任务栏打开已有窗口。','留白 · Focus',64)
            return
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except (OSError,AttributeError):
            pass
    root=tk.Tk()
    App(root)
    root.mainloop()
    if mutex:
        kernel.CloseHandle.argtypes=[ctypes.c_void_p]
        kernel.CloseHandle(mutex)


if __name__=='__main__':
    main()
