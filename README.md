# 留白 · Focus

一个离线 Windows 番茄钟。专注、短休息、长休息，配合每日记录与最近七天趋势。

紧凑版默认窗口为 420×540，迷你模式为 320×176。主页面只保留计时、当前任务和今日摘要；图表与完整片段列表放在“记录”页。

## 使用

解压发行包，双击 `StillFocus.exe`。无需安装 Python、登录账号或连接网络。

- 默认专注 25 分钟、短休息 5 分钟、长休息 15 分钟；每完成 4 次专注进入长休息。
- 点击开始后计时，空格键开始/暂停；编辑任务名称时空格正常输入。
- 点击“迷你”或按 Ctrl+M 切换小窗口；默认置顶，可点击“已置顶”取消。点击“展开”或按 Esc 返回主界面。切换窗口不会中断计时。
- 点击“记录”或按 Ctrl+H 查看历史，按 Esc 返回。按日期切换，片段支持翻页，不限于最近几条。
- 时间结束弹窗提醒，可关闭提示音。下一阶段需手动开始。
- 暂停、重置、切换模式、退出前会结算已专注时间；未完成的专注仍计入分钟，不计为完成的番茄。
- 关闭程序保存当前进度，重开后保持暂停。每 10 秒保存一次检查点，异常断电最多可能丢失最后约 10 秒。
- 电脑休眠或主事件循环中断超过 5 秒会暂停，空缺时间不计入专注。程序关闭后不在后台运行，也不会继续提醒。
- 每日记录按电脑本地日期统计，跨午夜自动分段。完成次数按结束当天统计。
- 点击顶部“记录”查看七天趋势和当天记录；设置里可打开数据文件夹。

## 隐私

完整说明见 [PRIVACY.md](PRIVACY.md)。

无需密钥，不含个人账号或预置记录，不采集访问域名，不上报数据。
记录保存在 `%LOCALAPPDATA%\StillFocus\focus.json`，包含任务名称、时长和时间，因此请勿公开此文件。
没有设置开机启动、自动更新、系统代理或浏览器登录。

## 源码

Python 3.12 / Tk 8.6，运行无需第三方依赖：

```powershell
python app.py
python -B -m unittest -v
```

构建依赖见 `requirements-build.txt`（PyInstaller、Pillow）：

```powershell
python -m pip install -r requirements-build.txt
python make_icon.py
python -m PyInstaller --noconfirm --clean --onefile --windowed --name StillFocus --icon assets/focus.ico --add-data "assets/focus.ico;assets" --exclude-module _hashlib app.py
```

Windows 发行包尚未进行代码签名。

## 设计参考

参考 [Windows 专注](https://support.microsoft.com/en-us/windows/experience/focus-stay-on-task-without-distractions-in-windows) 的小计时窗口与展开方式，以及 [Pomro](https://pomro.app/) 的紧凑、可置顶视图；计时、统计和界面代码均在本项目实现。
