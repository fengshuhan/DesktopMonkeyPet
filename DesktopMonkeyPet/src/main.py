import ctypes
import os
import random
import sys
import time
import winsound
from ctypes import wintypes

from PySide6.QtCore import QPoint, QRect, QSize, Qt, QTimer
from PySide6.QtGui import QAction, QContextMenuEvent, QCursor, QIcon, QPixmap, QTransform
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon, QWidget

USER32 = ctypes.windll.user32
DWMWA_EXTENDED_FRAME_BOUNDS = 9
GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x80
WS_EX_NOACTIVATE = 0x08000000
WS_EX_LAYERED = 0x80000


def rect_from_hwnd(hwnd):
    r = wintypes.RECT()
    if USER32.GetWindowRect(hwnd, ctypes.byref(r)):
        return QRect(r.left, r.top, r.right - r.left, r.bottom - r.top)
    return QRect()


def visible_app_windows(exclude_hwnds):
    out = []
    shell = USER32.GetShellWindow()

    @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    def enum_proc(hwnd, _):
        if hwnd in exclude_hwnds or hwnd == shell:
            return True
        if not USER32.IsWindowVisible(hwnd):
            return True
        if USER32.IsIconic(hwnd):
            return True
        ex = USER32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        if ex & WS_EX_TOOLWINDOW:
            return True
        title_len = USER32.GetWindowTextLengthW(hwnd)
        if title_len <= 0:
            return True
        r = rect_from_hwnd(hwnd)
        if r.width() >= 120 and r.height() >= 60:
            out.append(r)
        return True

    USER32.EnumWindows(enum_proc, 0)
    return out


class PetState:
    def __init__(self, screen):
        self.screen = screen
        self.w = 108
        self.h = 108
        self.x = random.randint(0, max(0, screen.width() - self.w))
        self.y = random.randint(0, max(0, screen.height() - self.h - 80))
        self.vx = random.choice([-1, 1]) * random.uniform(0.7, 1.7)
        self.vy = 0.0
        self.mode = random.choice(["walk", "walk", "idle", "jump"])
        self.mode_until = time.monotonic() + random.uniform(0.8, 3.0)
        self.platform_y = float(screen.height() - 8)
        self.facing = 1 if self.vx >= 0 else -1
        self.stuck = 0.0
        self.jump_cd = random.uniform(0.2, 1.8)

    def choose(self):
        now = time.monotonic()
        if now < self.mode_until:
            return
        self.mode = random.choices(["walk", "idle", "jump", "cling"], [5, 2, 2, 1])[0]
        self.mode_until = now + random.uniform(0.8, 2.8)
        if self.mode == "walk":
            self.vx = random.choice([-1, 1]) * random.uniform(0.7, 2.0)
        elif self.mode == "idle":
            self.vx = 0
        elif self.mode == "jump":
            self.vy = -random.uniform(7.0, 10.0)
            self.vx = random.choice([-1, 1]) * random.uniform(1.2, 2.5)
        else:
            self.vx = random.choice([-1, 1]) * random.uniform(0.8, 1.6)


class PetWindow(QWidget):
    def __init__(self, app, index, pixmap):
        super().__init__(None, Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint)
        self.app = app
        self.index = index
        self.pixmap = pixmap
        self.state = PetState(app.screen_geo)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setFixedSize(108, 108)
        self.show()
        self.move(int(self.state.x), int(self.state.y))

    def paintEvent(self, event):
        from PySide6.QtGui import QPainter
        p = QPainter(self)
        p.setRenderHint(QPainter.SmoothPixmapTransform, True)
        pm = self.pixmap
        if self.state.facing < 0:
            pm = pm.transformed(QTransform().scale(-1, 1))
        # Tiny bounce makes the still photo feel alive.
        bob = int(2 * abs(__import__('math').sin(time.monotonic() * 7 + self.index)))
        p.drawPixmap(0, bob, pm.scaled(108, 108, Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def contextMenuEvent(self, event: QContextMenuEvent):
        menu = QMenu(self)
        call = menu.addAction("🔊 叫爸爸")
        menu.addSeparator()
        add = menu.addAction("➕ 再来一只")
        pause = menu.addAction("⏸ 暂停全部" if not self.app.paused else "▶ 继续全部")
        exit_action = menu.addAction("✕ 退出")
        action = menu.exec(QCursor.pos())
        if action == call:
            self.app.play_dad()
        elif action == add:
            self.app.add_pet()
        elif action == pause:
            self.app.paused = not self.app.paused
        elif action == exit_action:
            self.app.quit()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.state.vy = -8.5
            self.state.vx = random.choice([-1, 1]) * 2.5
            self.update()
            event.accept()


class MonkeyApp:
    def __init__(self):
        self.qt = QApplication.instance()
        self.qt.setQuitOnLastWindowClosed(False)
        self.screen_geo = self.qt.primaryScreen().geometry()
        self.pets = []
        self.paused = False
        self.max_pets = 12
        self.pixmap = self.load_character()
        self.tray = QSystemTrayIcon(QIcon(self.pixmap), self.qt)
        self.tray.setToolTip("桌面猴群")
        self.menu = QMenu()
        self.build_menu()
        self.tray.setContextMenu(self.menu)
        self.tray.show()
        for _ in range(8):
            self.add_pet()
        self.timer = QTimer()
        self.timer.timeout.connect(self.tick)
        self.timer.start(30)
        self.window_timer = QTimer()
        self.window_timer.timeout.connect(self.refresh_platforms)
        self.window_timer.start(1000)
        self.platforms = []
        self.refresh_platforms()

    def load_character(self):
        path = os.path.join(os.path.dirname(__file__), "..", "assets", "character.png")
        pm = QPixmap(os.path.abspath(path))
        if pm.isNull():
            # Fallback: a simple transparent monkey-face glyph.
            pm = QPixmap(108, 108)
            pm.fill(Qt.transparent)
        return pm

    def build_menu(self):
        self.menu.clear()
        title = self.menu.addAction("🐒 桌面猴群")
        title.setEnabled(False)
        self.menu.addSeparator()
        add = self.menu.addAction("➕ 增加一只")
        remove = self.menu.addAction("➖ 减少一只")
        pause = self.menu.addAction("⏸ 暂停 / 继续")
        hide = self.menu.addAction("👻 隐藏 / 显示")
        self.menu.addSeparator()
        audio = self.menu.addAction("🔊 右键音频：" + ("已设置" if self.audio_path() else "未设置"))
        audio.setEnabled(False)
        exit_action = self.menu.addAction("✕ 退出全部")
        add.triggered.connect(self.add_pet)
        remove.triggered.connect(self.remove_pet)
        pause.triggered.connect(self.toggle_pause)
        hide.triggered.connect(self.toggle_visible)
        exit_action.triggered.connect(self.quit)

    def audio_path(self):
        return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "assets", "dad.wav"))

    def play_dad(self):
        p = self.audio_path()
        if os.path.exists(p) and os.path.getsize(p) > 44:
            try:
                winsound.PlaySound(p, winsound.SND_FILENAME | winsound.SND_ASYNC)
                return
            except Exception:
                pass
        self.tray.showMessage("桌面猴群", "还没有设置 dad.wav，先把音频放进 assets 文件夹即可。", QSystemTrayIcon.Information, 2200)

    def add_pet(self):
        if len(self.pets) >= self.max_pets:
            return
        self.pets.append(PetWindow(self, len(self.pets), self.pixmap))
        self.build_menu()

    def remove_pet(self):
        if self.pets:
            pet = self.pets.pop()
            pet.close()
        self.build_menu()

    def toggle_pause(self):
        self.paused = not self.paused
        self.build_menu()

    def toggle_visible(self):
        any_visible = any(p.isVisible() for p in self.pets)
        for p in self.pets:
            p.setVisible(not any_visible)

    def refresh_platforms(self):
        self.platforms = visible_app_windows({int(p.winId()) for p in self.pets})

    def nearest_platform(self, x, y, w, h):
        best = float(self.screen_geo.bottom())
        for r in self.platforms:
            if x + w * 0.35 < r.right() and x + w * 0.65 > r.left():
                top = r.top()
                if top >= y + h - 4 and top < best:
                    best = top
        return best

    def tick(self):
        if self.paused:
            return
        for pet in self.pets:
            s = pet.state
            s.choose()
            dt = 0.03
            s.vy += 0.42
            s.x += s.vx
            s.y += s.vy
            if s.vx:
                s.facing = 1 if s.vx > 0 else -1
            if s.x <= 0:
                s.x = 0; s.vx = abs(s.vx)
            if s.x + s.w >= self.screen_geo.width():
                s.x = self.screen_geo.width() - s.w; s.vx = -abs(s.vx)

            floor = self.nearest_platform(s.x, s.y, s.w, s.h)
            if s.y + s.h >= floor and s.vy >= 0:
                s.y = floor - s.h
                s.vy = 0
                if s.mode == "jump":
                    s.mode = "walk"
                    s.mode_until = time.monotonic() + random.uniform(0.5, 1.5)
                if random.random() < 0.004:
                    s.vy = -random.uniform(7, 10)

            # Occasional window-edge climb: run upward beside a window then hop off.
            if s.mode == "cling" and self.platforms:
                for r in self.platforms:
                    if abs((s.x + s.w) - r.left()) < 10 and r.top() < s.y < r.bottom():
                        s.x = r.left() - s.w + 2
                        s.y -= 1.7
                        if s.y < r.top() - s.h:
                            s.mode = "jump"; s.vy = -8; s.vx = 2.0
                        break
            pet.move(int(s.x), int(s.y))
            pet.update()

    def quit(self):
        for p in self.pets:
            p.close()
        self.tray.hide()
        self.qt.quit()


def main():
    app = QApplication(sys.argv)
    MonkeyApp()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
