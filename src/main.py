import ctypes
import logging
import math
import os
import random
import sys
import time
from ctypes import wintypes

from PySide6.QtCore import Qt, QTimer, QRect
from PySide6.QtGui import QIcon, QPainter, QPixmap, QTransform, QImage
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon, QWidget
from PIL import Image

try:
    import winsound
except Exception:
    winsound = None

APP_NAME = "Desktop Monkey Pet"
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
CHARACTER_PATH = os.path.join(ASSETS_DIR, "character.png")
DAD_PATH = os.path.join(ASSETS_DIR, "dad.wav")
LOG_PATH = os.path.join(BASE_DIR, "DesktopMonkeyPet.log")

logging.basicConfig(
    filename=LOG_PATH,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    encoding="utf-8",
)
log = logging.getLogger(APP_NAME)

USER32 = ctypes.windll.user32
GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x80

def screen_rect(app):
    screen = app.primaryScreen()
    return screen.availableGeometry() if screen else QRect(0, 0, 1280, 720)

def window_rect(hwnd):
    r = wintypes.RECT()
    if USER32.GetWindowRect(hwnd, ctypes.byref(r)):
        return QRect(r.left, r.top, r.right-r.left, r.bottom-r.top)
    return QRect()

def visible_windows(exclude):
    result = []
    shell = USER32.GetShellWindow()

    @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    def enum_proc(hwnd, _):
        try:
            if hwnd in exclude or hwnd == shell:
                return True
            if not USER32.IsWindowVisible(hwnd) or USER32.IsIconic(hwnd):
                return True
            ex = USER32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            if ex & WS_EX_TOOLWINDOW:
                return True
            if USER32.GetWindowTextLengthW(hwnd) == 0:
                return True
            r = window_rect(hwnd)
            if r.width() >= 160 and r.height() >= 80:
                result.append(r)
        except Exception:
            pass
        return True

    USER32.EnumWindows(enum_proc, 0)
    return result

def make_tray_icon():
    # Deliberately draw a visible icon rather than using the large character PNG.
    pm = QPixmap(64, 64)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(Qt.yellow)
    p.setPen(Qt.black)
    p.drawEllipse(5, 5, 54, 54)
    p.setBrush(Qt.black)
    p.drawEllipse(19, 22, 7, 9)
    p.drawEllipse(38, 22, 7, 9)
    p.drawArc(18, 28, 28, 22, 200 * 16, 140 * 16)
    p.end()
    return QIcon(pm)

def fallback_pixmap(size=140):
    # Visible fallback so a bad/missing PNG never results in "nothing".
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(Qt.yellow)
    p.setPen(Qt.black)
    p.drawEllipse(18, 15, size-36, size-30)
    p.setBrush(Qt.black)
    p.drawEllipse(43, 55, 13, 16)
    p.drawEllipse(size-56, 55, 13, 16)
    p.drawEllipse(size//2-8, 75, 16, 13)
    p.drawArc(45, 77, size-90, 35, 200*16, 140*16)
    p.end()
    return pm

class Pet:
    def __init__(self, app, index, pixmap):
        self.app = app
        self.index = index
        self.w = 140
        self.h = 140
        sr = app.screen_rect
        self.x = random.randint(sr.left(), max(sr.left(), sr.right()-self.w))
        self.y = random.randint(sr.top(), max(sr.top(), sr.bottom()-self.h-20))
        self.vx = random.choice([-1, 1]) * random.uniform(0.8, 2.2)
        self.vy = 0.0
        self.state = random.choice(["walk", "walk", "idle", "jump"])
        self.next_state = time.monotonic() + random.uniform(.7, 2.5)
        self.facing = 1 if self.vx >= 0 else -1
        self.window_mode = False
        self.window_target = None

        self.widget = PetWidget(app, self, pixmap)
        self.widget.show()
        self.widget.move(int(self.x), int(self.y))
        self.widget.raise_()

    def choose_state(self):
        now = time.monotonic()
        if now < self.next_state:
            return
        self.state = random.choices(
            ["walk", "idle", "jump", "walk", "window"],
            weights=[4, 2, 2, 4, 1],
        )[0]
        self.next_state = now + random.uniform(.8, 3.2)
        if self.state == "idle":
            self.vx = 0
        elif self.state == "walk":
            self.vx = random.choice([-1, 1]) * random.uniform(.8, 2.5)
        elif self.state == "jump":
            self.vy = -random.uniform(8.5, 12)
            self.vx = random.choice([-1, 1]) * random.uniform(1.5, 3)
        elif self.state == "window":
            self.vx = random.choice([-1, 1]) * random.uniform(.8, 1.8)

class PetWidget(QWidget):
    def __init__(self, app, pet, pixmap):
        flags = Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint
        super().__init__(None, flags)
        self.app = app
        self.pet = pet
        self.pixmap = pixmap
        self.setFixedSize(pet.w, pet.h)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setWindowFlag(Qt.WindowDoesNotAcceptFocus, True)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        pm = self.pixmap
        if self.pet.facing < 0:
            pm = pm.transformed(QTransform().scale(-1, 1))
        bob = int(abs(math.sin(time.monotonic()*6 + self.pet.index))*3)
        target = QRect(4, 4+bob, self.width()-8, self.height()-8)
        p.drawPixmap(target, pm)
        p.end()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.pet.vy = -10
            self.pet.vx = random.choice([-1, 1]) * 3
            e.accept()
        elif e.button() == Qt.RightButton:
            self.app.play_dad()
            e.accept()

    def contextMenuEvent(self, e):
        menu = QMenu()
        a1 = menu.addAction("🔊 叫爸爸")
        a2 = menu.addAction("➕ 再来一只")
        a3 = menu.addAction("⏸ 暂停 / 继续")
        a4 = menu.addAction("✕ 退出")
        chosen = menu.exec(e.globalPos())
        if chosen == a1:
            self.app.play_dad()
        elif chosen == a2:
            self.app.add_pet()
        elif chosen == a3:
            self.app.paused = not self.app.paused
        elif chosen == a4:
            self.app.quit()

class MonkeyApp:
    def __init__(self, qt):
        self.qt = qt
        self.screen_rect = screen_rect(qt)
        self.pets = []
        self.paused = False
        self.max_pets = 15
        self.platforms = []
        self.visible = True

        self.pixmap = self.load_character()
        self.tray = QSystemTrayIcon(make_tray_icon(), qt)
        self.tray.setToolTip("桌面猴群")
        self.menu = QMenu()
        self.rebuild_menu()
        self.tray.setContextMenu(self.menu)
        self.tray.show()

        for _ in range(6):
            self.add_pet()

        self.platform_timer = QTimer()
        self.platform_timer.timeout.connect(self.refresh_platforms)
        self.platform_timer.start(1000)

        self.timer = QTimer()
        self.timer.timeout.connect(self.tick)
        self.timer.start(30)

        self.refresh_platforms()
        log.info("Started successfully. pets=%d image=%s size=%s",
                 len(self.pets), CHARACTER_PATH, self.pixmap.size())

    def load_character(self):
        try:
            with Image.open(CHARACTER_PATH) as im:
                im = im.convert("RGBA")
                width, height = im.size
                raw = im.tobytes("raw", "RGBA")
    
            image = QImage(
                raw,
                width,
                height,
                width * 4,
                QImage.Format_RGBA8888
            ).copy()
    
            pm = QPixmap.fromImage(image)
    
            if pm.isNull():
                raise RuntimeError("QPixmap.fromImage returned a null pixmap")
    
            log.info(
                "Loaded character.png via Pillow: %dx%d alpha=%s",
                pm.width(),
                pm.height(),
                pm.hasAlphaChannel()
            )
            return pm

            except Exception as exc:
                log.exception(
                    "character.png could not be loaded via Pillow: %s",
                    exc
                )
                return fallback_pixmap()
    def rebuild_menu(self):
        self.menu.clear()
        title = self.menu.addAction("🐒 桌面猴群")
        title.setEnabled(False)
        self.menu.addSeparator()
        a = self.menu.addAction(f"➕ 增加一只（{len(self.pets)}/{self.max_pets}）")
        r = self.menu.addAction("➖ 减少一只")
        p = self.menu.addAction("▶ 继续" if self.paused else "⏸ 暂停")
        h = self.menu.addAction("👻 隐藏 / 显示")
        self.menu.addSeparator()
        audio = "已设置" if os.path.isfile(DAD_PATH) and os.path.getsize(DAD_PATH) > 44 else "未设置"
        info = self.menu.addAction(f"🔊 右键音频：{audio}")
        info.setEnabled(False)
        self.menu.addSeparator()
        q = self.menu.addAction("✕ 退出全部")
        a.triggered.connect(self.add_pet)
        r.triggered.connect(self.remove_pet)
        p.triggered.connect(self.toggle_pause)
        h.triggered.connect(self.toggle_visible)
        q.triggered.connect(self.quit)

    def add_pet(self):
        if len(self.pets) >= self.max_pets:
            return
        pet = Pet(self, len(self.pets), self.pixmap)
        self.pets.append(pet)
        self.rebuild_menu()

    def remove_pet(self):
        if self.pets:
            pet = self.pets.pop()
            pet.widget.close()
        self.rebuild_menu()

    def toggle_pause(self):
        self.paused = not self.paused
        self.rebuild_menu()

    def toggle_visible(self):
        self.visible = not self.visible
        for pet in self.pets:
            pet.widget.setVisible(self.visible)

    def refresh_platforms(self):
        try:
            exclude = {int(p.widget.winId()) for p in self.pets}
            self.platforms = visible_windows(exclude)
        except Exception as exc:
            log.exception("Platform refresh failed: %s", exc)

    def landing_y(self, pet):
        # Desktop bottom plus tops of normal application windows.
        bottom = self.screen_rect.bottom()
        best = float(bottom)
        x1, x2 = pet.x + 25, pet.x + pet.w - 25
        for r in self.platforms:
            if x2 > r.left() and x1 < r.right() and r.top() >= pet.y:
                if r.top() < best:
                    best = r.top()
        return best

    def tick(self):
        if self.paused:
            return
        for pet in self.pets:
            try:
                s = pet
                s.choose_state()

                s.vy += 0.42
                s.x += s.vx
                s.y += s.vy

                if s.vx:
                    s.facing = 1 if s.vx > 0 else -1

                left = self.screen_rect.left()
                right = self.screen_rect.right() - s.w
                if s.x <= left:
                    s.x = left
                    s.vx = abs(s.vx)
                elif s.x >= right:
                    s.x = right
                    s.vx = -abs(s.vx)

                floor = self.landing_y(s)
                if s.y + s.h >= floor and s.vy >= 0:
                    s.y = floor - s.h
                    s.vy = 0
                    if random.random() < 0.006:
                        s.vy = -random.uniform(8, 11)

                # Gentle flocking: nearby pets occasionally move toward each other.
                for other in self.pets:
                    if other is s:
                        continue
                    dx = other.x - s.x
                    dy = other.y - s.y
                    if abs(dx) < 220 and abs(dy) < 90 and random.random() < 0.002:
                        s.vx += 0.7 if dx > 0 else -0.7

                # Avoid overlapping too much.
                for other in self.pets:
                    if other is s:
                        continue
                    if abs(other.x-s.x) < 65 and abs(other.y-s.y) < 55:
                        s.vx += -0.35 if other.x > s.x else 0.35

                s.vx = max(-3.5, min(3.5, s.vx))
                s.widget.move(int(s.x), int(s.y))
                s.widget.update()
            except Exception:
                log.exception("Pet tick failed")

    def play_dad(self):
        if winsound and os.path.isfile(DAD_PATH) and os.path.getsize(DAD_PATH) > 44:
            try:
                winsound.PlaySound(DAD_PATH, winsound.SND_FILENAME | winsound.SND_ASYNC)
                return
            except Exception:
                log.exception("Audio playback failed")
        self.tray.showMessage(
            "桌面猴群",
            "还没有 dad.wav。\n以后把音频放进 assets\\dad.wav 即可。",
            QSystemTrayIcon.Information,
            2500,
        )

    def quit(self):
        log.info("Exiting.")
        for pet in self.pets:
            pet.widget.close()
        self.tray.hide()
        self.qt.quit()

def main():
    try:
        app = QApplication(sys.argv)
        app.setQuitOnLastWindowClosed(False)
        MonkeyApp(app)
        return app.exec()
    except Exception:
        log.exception("Fatal startup error")
        raise

if __name__ == "__main__":
    main()
