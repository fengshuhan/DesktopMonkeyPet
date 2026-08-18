import ctypes
import math
import os
import random
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QPoint, QRect, QTimer, Qt, Signal
from PySide6.QtGui import QBitmap, QContextMenuEvent, QImage, QPainter, QPixmap, QTransform, QAction
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon, QWidget

if sys.platform != "win32":
    raise SystemExit("DesktopMonkeyPet is a Windows-only application.")

import win32con
import win32gui

APP_NAME = "Desktop Monkey Pet"
BASE_SIZE = 150
DEFAULT_COUNT = 8
FPS = 30
GRAVITY = 1100.0
MAX_SPEED = 260.0


def resource_path(*parts: str) -> str:
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
    return str(root.joinpath(*parts))


@dataclass
class Obstacle:
    rect: QRect
    title: str


class WindowScanner:
    def __init__(self, own_hwnds):
        self.own_hwnds = set(own_hwnds)
        self._last = 0.0
        self.obstacles = []

    def refresh(self):
        now = time.monotonic()
        if now - self._last < 0.25:
            return self.obstacles
        self._last = now
        found = []

        def callback(hwnd, _):
            try:
                if hwnd in self.own_hwnds or not win32gui.IsWindowVisible(hwnd):
                    return True
                if win32gui.IsIconic(hwnd):
                    return True
                ex = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
                if ex & win32con.WS_EX_TOOLWINDOW:
                    return True
                title = win32gui.GetWindowText(hwnd).strip()
                if not title:
                    return True
                left, top, right, bottom = win32gui.GetWindowRect(hwnd)
                if right - left < 80 or bottom - top < 60:
                    return True
                # Ignore the shell/desktop windows.
                cls = win32gui.GetClassName(hwnd)
                if cls in {"Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd"}:
                    return True
                found.append(Obstacle(QRect(left, top, right - left, bottom - top), title))
            except win32gui.error:
                pass
            return True

        win32gui.EnumWindows(callback, None)
        self.obstacles = found
        return found


def screen_geometry(app: QApplication) -> QRect:
    # Primary-screen-first is sufficient for the first prototype; pets are allowed
    # to roam over the virtual desktop if multiple monitors are present.
    screens = app.screens()
    if not screens:
        return QRect(0, 0, 1920, 1080)
    united = screens[0].geometry()
    for screen in screens[1:]:
        united = united.united(screen.geometry())
    return united


class PetWindow(QWidget):
    right_clicked = Signal(object)

    def __init__(self, manager, index: int, pixmap: QPixmap):
        super().__init__(None, Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint)
        self.manager = manager
        self.index = index
        self.base_pixmap = pixmap
        self.scale = random.uniform(0.62, 0.92)
        self.w = BASE_SIZE
        self.h = BASE_SIZE
        self.resize(self.w, self.h)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setContextMenuPolicy(Qt.DefaultContextMenu)
        self.setWindowTitle(f"Monkey Pet {index}")

        self.x = random.uniform(manager.desktop.left() + 20, manager.desktop.right() - self.w - 20)
        self.y = random.uniform(manager.desktop.top() + 40, manager.desktop.bottom() - self.h - 180)
        self.vx = random.choice([-1, 1]) * random.uniform(50, 150)
        self.vy = 0.0
        self.facing = 1 if self.vx >= 0 else -1
        self.phase = random.random() * math.tau
        self.bob = 0.0
        self.state = "air"
        self.state_until = 0.0
        self.jump_cooldown = random.uniform(0.8, 3.0)
        self.last_update = time.monotonic()
        self.show()
        self._apply_mask()

    def _apply_mask(self):
        img = self.base_pixmap.toImage().scaled(self.w, self.h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        alpha = img.createAlphaMask()
        self.setMask(QBitmap.fromImage(alpha))

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        t = time.monotonic()
        tilt = math.sin(self.phase + t * 10.0) * (8 if self.state in {"walk", "climb"} else 3)
        bob = math.sin(self.phase + t * 12.0) * (4 if self.state == "walk" else 1.5)
        transform = QTransform()
        transform.translate(self.w / 2, self.h / 2 + bob)
        transform.rotate(tilt)
        if self.facing < 0:
            transform.scale(-1, 1)
        transform.translate(-self.w / 2, -self.h / 2)
        painter.setTransform(transform)
        target = QRect(0, 0, self.w, self.h)
        painter.drawPixmap(target, self.base_pixmap.scaled(self.w, self.h, Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def contextMenuEvent(self, event: QContextMenuEvent):
        menu = QMenu(self)
        play = QAction("叫爸爸", self)
        play.triggered.connect(lambda: self.manager.play_audio())
        menu.addAction(play)
        menu.addSeparator()
        dismiss = QAction("移除这只猴子", self)
        dismiss.triggered.connect(lambda: self.manager.remove_pet(self))
        menu.addAction(dismiss)
        menu.exec(event.globalPos())
        event.accept()

    def mousePressEvent(self, event):
        if event.button() == Qt.RightButton:
            self.manager.play_audio()
            event.accept()
            return
        if event.button() == Qt.LeftButton:
            self.vy = -520
            self.vx += random.choice([-80, 80])
            self.state = "air"
            event.accept()

    def advance(self, dt: float, obstacles):
        now = time.monotonic()
        self.jump_cooldown -= dt
        self.phase += dt
        bounds = self.manager.desktop

        # Occasional behavior changes keep the group organic rather than synchronized.
        if now > self.state_until:
            r = random.random()
            if self.state != "air" and r < 0.10:
                self.vy = -random.uniform(430, 620)
                self.state = "air"
                self.state_until = now + random.uniform(0.3, 0.8)
            elif r < 0.20:
                self.vx = random.choice([-1, 1]) * random.uniform(60, 170)
                self.state = "walk"
                self.state_until = now + random.uniform(0.7, 2.8)
            elif r < 0.25:
                self.vx *= 0.2
                self.state = "idle"
                self.state_until = now + random.uniform(0.5, 1.5)

        if self.state == "climb":
            self.y += self.vy * dt
            self.vy = random.choice([-1, 1]) * 70
        else:
            self.vy += GRAVITY * dt
            self.x += self.vx * dt
            self.y += self.vy * dt

        if self.vx:
            self.facing = 1 if self.vx > 0 else -1
        self.vx = max(-MAX_SPEED, min(MAX_SPEED, self.vx))

        # Screen boundaries.
        if self.x <= bounds.left():
            self.x = bounds.left()
            self.vx = abs(self.vx)
        if self.x + self.w >= bounds.right():
            self.x = bounds.right() - self.w
            self.vx = -abs(self.vx)
        if self.y <= bounds.top():
            self.y = bounds.top()
            self.vy = abs(self.vy) * 0.2

        floor_y = bounds.bottom()
        for obs in obstacles:
            r = obs.rect
            # Treat window top edges as platforms when horizontally overlapping.
            if self.x + self.w * 0.72 > r.left() and self.x + self.w * 0.28 < r.right():
                if self.vy >= 0 and self.y + self.h >= r.top() - 12 and self.y + self.h <= r.top() + 40:
                    floor_y = min(floor_y, r.top())

        if self.state != "climb" and self.y + self.h >= floor_y:
            self.y = floor_y - self.h
            if self.vy > 0:
                self.vy = 0
            self.state = "walk"
            # Occasionally use a window edge as a climb trigger.
            if random.random() < 0.015:
                edge = self._near_vertical_edge(obstacles)
                if edge:
                    self.state = "climb"
                    self.x = edge
                    self.vy = random.choice([-1, 1]) * 75
                    self.state_until = now + random.uniform(0.8, 2.2)

        if self.state == "climb" and now > self.state_until:
            self.state = "air"
            self.vy = -random.uniform(200, 380)

        self.move(int(self.x), int(self.y))
        self.update()

    def _near_vertical_edge(self, obstacles):
        center = self.x + self.w / 2
        best = None
        best_dist = 24
        for obs in obstacles:
            r = obs.rect
            for edge in (r.left() - self.w * 0.45, r.right() - self.w * 0.55):
                d = abs(center - edge)
                if d < best_dist and r.top() < self.y + self.h < r.bottom():
                    best = edge
                    best_dist = d
        return best


class PetManager:
    def __init__(self, app: QApplication):
        self.app = app
        self.desktop = screen_geometry(app)
        self.pets = []
        self.scanner = WindowScanner([])
        self.audio_output = QAudioOutput()
        self.audio_output.setVolume(1.0)
        self.player = QMediaPlayer()
        self.player.setAudioOutput(self.audio_output)
        self.audio_path = resource_path("assets", "dad.wav")

        img = QImage(resource_path("assets", "person.png"))
        if img.isNull():
            raise RuntimeError("assets/person.png could not be loaded")
        self.pixmap = QPixmap.fromImage(img)
        self.timer = QTimer()
        self.timer.timeout.connect(self.tick)
        self.last_tick = time.monotonic()
        self.timer.start(int(1000 / FPS))
        self.spawn(DEFAULT_COUNT)
        self.tray = self._make_tray()

    def _make_tray(self):
        tray = QSystemTrayIcon(self.app)
        tray.setToolTip(APP_NAME)
        menu = QMenu()
        add5 = QAction("再增加 5 只", menu)
        add5.triggered.connect(lambda: self.spawn(5))
        menu.addAction(add5)
        clear = QAction("清空猴子", menu)
        clear.triggered.connect(self.clear)
        menu.addAction(clear)
        menu.addSeparator()
        quit_action = QAction("退出", menu)
        quit_action.triggered.connect(self.app.quit)
        menu.addAction(quit_action)
        tray.setContextMenu(menu)
        tray.show()
        return tray

    def spawn(self, count):
        for _ in range(count):
            pet = PetWindow(self, len(self.pets) + 1, self.pixmap)
            self.pets.append(pet)
            self.scanner.own_hwnds.add(int(pet.winId()))

    def remove_pet(self, pet):
        if pet in self.pets:
            self.pets.remove(pet)
            self.scanner.own_hwnds.discard(int(pet.winId()))
            pet.close()

    def clear(self):
        for pet in self.pets[:]:
            self.remove_pet(pet)

    def play_audio(self):
        if not os.path.exists(self.audio_path) or os.path.getsize(self.audio_path) < 64:
            return
        self.player.setSource(self.audio_path)
        self.player.play()

    def tick(self):
        now = time.monotonic()
        dt = min(0.05, now - self.last_tick)
        self.last_tick = now
        obstacles = self.scanner.refresh()
        for pet in self.pets[:]:
            pet.advance(dt, obstacles)


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName(APP_NAME)
    manager = PetManager(app)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
