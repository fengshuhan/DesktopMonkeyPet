# Desktop Monkey Pet 🐒

Windows 桌面宠物原型：多只人物宠物在桌面上随机移动、跳跃，并把可见应用窗口当作简单的平台/障碍物。

## 当前功能
- 8 只宠物启动，可从托盘增加/减少，最多 12 只。
- 独立随机 AI：走动、待机、跳跃、贴边攀爬。
- 重力与窗口顶部平台检测。
- 屏幕左右边缘反弹。
- 左键点击宠物：让它跳起来。
- 右键宠物：`叫爸爸`，预留 `assets/dad.wav`。
- 系统托盘：暂停/继续、隐藏/显示、增减宠物、退出。
- GitHub Actions 自动生成 Windows EXE。

## 运行
```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python src/main.py
```

## 打包
```powershell
.\build.ps1
```

## 人物素材
程序读取 `assets/character.png`。需要透明背景 PNG。当前 ZIP 没有伪造声称已经从上一条聊天图片完成抠图；请把最终抠图文件放到该位置即可。

## 音频
将“叫爸爸”音频保存为 `assets/dad.wav`。没有音频时右键仍然可用，只会提示尚未设置。
