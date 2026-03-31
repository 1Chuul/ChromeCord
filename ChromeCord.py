import os
import sys
import json
import time
import threading

import psutil
import win32gui
from pypresence import Presence

from PySide6.QtCore import Qt, Signal, QObject, QPropertyAnimation, QEasingCurve, Property
from PySide6.QtGui import QFont, QColor, QPainter, QIcon, QAction
from PySide6.QtWidgets import (
    QApplication, QWidget, QFrame, QLabel, QPushButton, QVBoxLayout,
    QHBoxLayout, QCheckBox, QTextEdit, QMessageBox, QStackedWidget,
    QGraphicsOpacityEffect, QSystemTrayIcon, QMenu, QStyle
)

CLIENT_ID = "1488456026012385410"

running = False
rpc = None
worker_thread = None


def get_base_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


BASE_DIR = get_base_dir()
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
ICON_PATH = os.path.join(BASE_DIR, "icon.ico")


def save_config(config):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def load_config():
    default_config = {
        "show_youtube": True,
        "show_google": True,
        "show_other": True,
        "keep_presence_on_alt_tab": True
    }

    if not os.path.exists(CONFIG_PATH):
        save_config(default_config)
        return default_config

    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        for key, value in default_config.items():
            loaded.setdefault(key, value)
        return loaded
    except Exception:
        save_config(default_config)
        return default_config


config = load_config()


def is_chrome_running():
    for p in psutil.process_iter(["name"]):
        try:
            name = p.info["name"]
            if name and "chrome" in name.lower():
                return True
        except Exception:
            pass
    return False


def get_active_window_title():
    try:
        hwnd = win32gui.GetForegroundWindow()
        if hwnd == 0:
            return ""
        return win32gui.GetWindowText(hwnd)
    except Exception:
        return ""


def is_chrome_window(title: str) -> bool:
    t = title.lower()
    return "chrome" in t or "google chrome" in t


def clean_chrome_title(title: str) -> str:
    for suffix in [
        " - Google Chrome",
        " - Chrome",
        " - google chrome",
        " - chrome",
    ]:
        if title.endswith(suffix):
            return title[:-len(suffix)].strip()
    return title.strip()


class Bridge(QObject):
    status_changed = Signal(str, str)
    now_changed = Signal(str)
    log_added = Signal(str)


bridge = Bridge()


def add_log(text):
    now = time.strftime("%H:%M:%S")
    bridge.log_added.emit(f"[{now}] {text}")


def clear_rpc():
    global rpc
    try:
        if rpc:
            rpc.clear()
    except Exception:
        pass


def discord_loop():
    global running, rpc, config

    try:
        rpc = Presence(CLIENT_ID)
        rpc.connect()
        bridge.status_changed.emit("실행 중", "#57F287")
        add_log("Discord RPC 연결 성공")
    except Exception as e:
        running = False
        bridge.status_changed.emit("연결 실패", "#ED4245")
        add_log(f"Discord RPC 연결 실패: {e}")
        return

    last_title = ""
    last_details = "없음"
    start_time = int(time.time())

    while running:
        try:
            if is_chrome_running():
                title = get_active_window_title()

                if is_chrome_window(title):
                    clean = clean_chrome_title(title)

                    state = None
                    image = None

                    if "YouTube" in title and config.get("show_youtube", True):
                        state = "유튜브 시청 중 🎬"
                        image = "youtube"
                    elif "Google" in title and config.get("show_google", True):
                        state = "구글 검색 중 🔎"
                        image = "google"
                    elif config.get("show_other", True):
                        state = "인터넷 서핑 중 🌐"
                        image = "chrome"

                    if state:
                        if title != last_title:
                            rpc.update(
                                state=state,
                                details=clean[:128] if clean else "Chrome 사용 중",
                                large_image=image,
                                large_text=image,
                                start=start_time
                            )
                            last_title = title
                            last_details = clean if clean else "Chrome 사용 중"
                            bridge.now_changed.emit(last_details)
                            bridge.status_changed.emit("표시 중", "#57F287")
                            add_log(f"업데이트: {last_details}")
                    else:
                        clear_rpc()
                        last_title = "__hidden__"
                        last_details = "설정상 표시 안 함"
                        bridge.now_changed.emit(last_details)
                        bridge.status_changed.emit("대기 중", "#FEE75C")

                else:
                    if config.get("keep_presence_on_alt_tab", True):
                        bridge.now_changed.emit(last_details)
                        bridge.status_changed.emit("백그라운드 유지 중", "#FEE75C")
                    else:
                        clear_rpc()
                        last_title = "__not_chrome__"
                        last_details = "Chrome 창이 활성화되어 있지 않음"
                        bridge.now_changed.emit(last_details)
                        bridge.status_changed.emit("대기 중", "#FEE75C")

            else:
                if last_title != "__chrome_closed__":
                    clear_rpc()
                    last_title = "__chrome_closed__"
                    last_details = "Chrome가 실행 중이 아님"
                    bridge.now_changed.emit(last_details)
                    bridge.status_changed.emit("대기 중", "#FEE75C")
                    add_log("Chrome 미실행 상태")

        except Exception as e:
            bridge.status_changed.emit("오류 발생", "#ED4245")
            add_log(f"오류: {e}")

        time.sleep(2)

    clear_rpc()
    rpc = None
    bridge.status_changed.emit("중지됨", "#B5BAC1")
    bridge.now_changed.emit("없음")
    add_log("Discord RPC 중지")


class AnimatedButton(QPushButton):
    def __init__(self, text, base="#5865F2", hover="#6D78F7", press="#4752C4"):
        super().__init__(text)
        self._bg = QColor(base)
        self.base_color = QColor(base)
        self.hover_color = QColor(hover)
        self.press_color = QColor(press)

        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(44)

        self.setStyleSheet("""
            QPushButton {
                color: white;
                border: none;
                border-radius: 10px;
                padding: 12px 14px;
                text-align: left;
                font-weight: 700;
                background: transparent;
            }
        """)

        self.anim = QPropertyAnimation(self, b"bgColor", self)
        self.anim.setDuration(140)
        self.anim.setEasingCurve(QEasingCurve.OutCubic)

    def get_color(self):
        return self._bg

    def set_color(self, c):
        self._bg = c
        self.update()

    bgColor = Property(QColor, get_color, set_color)

    def animate_to(self, color):
        self.anim.stop()
        self.anim.setStartValue(self._bg)
        self.anim.setEndValue(QColor(color))
        self.anim.start()

    def enterEvent(self, event):
        self.animate_to(self.hover_color)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.animate_to(self.base_color)
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        self.animate_to(self.press_color)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if self.rect().contains(event.position().toPoint()):
            self.animate_to(self.hover_color)
        else:
            self.animate_to(self.base_color)
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(self._bg)
        painter.drawRoundedRect(self.rect(), 10, 10)
        super().paintEvent(event)


class MenuButton(QPushButton):
    def __init__(self, text):
        super().__init__(text)
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(44)
        self.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #B5BAC1;
                font-weight: 600;
                border: none;
                border-radius: 10px;
                padding: 12px 14px;
                text-align: left;
            }
            QPushButton:hover {
                background: #35373C;
                color: white;
            }
        """)


class ChromecordWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.drag_pos = None
        self.is_quitting = False

        self.setWindowTitle("Chromecord")
        self.setMinimumSize(980, 620)
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

        self.init_ui()
        self.apply_styles()
        self.load_config_to_ui()
        self.init_tray()

        bridge.status_changed.connect(self.set_status)
        bridge.now_changed.connect(self.set_now)
        bridge.log_added.connect(self.append_log)

        self.setWindowOpacity(0.0)
        self.fade = QPropertyAnimation(self, b"windowOpacity", self)
        self.fade.setDuration(250)
        self.fade.setStartValue(0.0)
        self.fade.setEndValue(1.0)
        self.fade.setEasingCurve(QEasingCurve.OutCubic)

    def init_tray(self):
        icon = QIcon(ICON_PATH) if os.path.exists(ICON_PATH) else self.style().standardIcon(QStyle.SP_ComputerIcon)
        self.tray = QSystemTrayIcon(icon, self)

        menu = QMenu()

        show_action = QAction("열기", self)
        start_action = QAction("실행", self)
        stop_action = QAction("중지", self)
        quit_action = QAction("완전 종료", self)

        show_action.triggered.connect(self.show_window)
        start_action.triggered.connect(self.start_rpc)
        stop_action.triggered.connect(self.stop_rpc)
        quit_action.triggered.connect(self.exit_app)

        menu.addAction(show_action)
        menu.addAction(start_action)
        menu.addAction(stop_action)
        menu.addSeparator()
        menu.addAction(quit_action)

        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self.tray_clicked)
        self.tray.show()

    def tray_clicked(self, reason):
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self.show_window()

    def show_window(self):
        self.show()
        self.raise_()
        self.activateWindow()

    def exit_app(self):
        global running
        self.is_quitting = True
        running = False
        clear_rpc()
        self.tray.hide()
        QApplication.quit()

    def init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.container = QFrame()
        self.container.setObjectName("mainContainer")

        container_layout = QVBoxLayout(self.container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)

        self.titlebar = QFrame()
        self.titlebar.setObjectName("titlebar")
        self.titlebar.setFixedHeight(42)

        titlebar_layout = QHBoxLayout(self.titlebar)
        titlebar_layout.setContentsMargins(14, 0, 10, 0)

        self.title_label = QLabel("Chromecord")
        self.title_label.setObjectName("windowTitle")

        titlebar_layout.addWidget(self.title_label)
        titlebar_layout.addStretch()

        self.min_btn = QPushButton("—")
        self.close_btn = QPushButton("✕")
        self.min_btn.setObjectName("titleBtn")
        self.close_btn.setObjectName("closeBtn")
        self.min_btn.clicked.connect(self.showMinimized)
        self.close_btn.clicked.connect(self.close)

        titlebar_layout.addWidget(self.min_btn)
        titlebar_layout.addWidget(self.close_btn)

        content = QHBoxLayout()
        content.setContentsMargins(0, 0, 0, 0)
        content.setSpacing(0)

        self.sidebar = QFrame()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setFixedWidth(220)

        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(14, 16, 14, 16)
        sidebar_layout.setSpacing(10)

        logo = QLabel("C")
        logo.setAlignment(Qt.AlignCenter)
        logo.setFixedSize(54, 54)
        logo.setObjectName("logo")

        app_name = QLabel("Chromecord")
        app_name.setObjectName("appName")

        app_sub = QLabel("Discord Rich Presence")
        app_sub.setObjectName("appSub")

        sidebar_layout.addWidget(logo, alignment=Qt.AlignHCenter)
        sidebar_layout.addWidget(app_name, alignment=Qt.AlignHCenter)
        sidebar_layout.addWidget(app_sub, alignment=Qt.AlignHCenter)
        sidebar_layout.addSpacing(18)

        self.home_btn = MenuButton("Home")
        self.settings_btn = MenuButton("Settings")
        self.logs_btn = MenuButton("Logs")

        self.home_btn.clicked.connect(lambda: self.switch_page(0))
        self.settings_btn.clicked.connect(lambda: self.switch_page(1))
        self.logs_btn.clicked.connect(lambda: self.switch_page(2))

        sidebar_layout.addWidget(self.home_btn)
        sidebar_layout.addWidget(self.settings_btn)
        sidebar_layout.addWidget(self.logs_btn)
        sidebar_layout.addStretch()

        self.status_badge = QLabel("중지됨")
        self.status_badge.setObjectName("statusBadge")
        self.status_badge.setAlignment(Qt.AlignCenter)
        self.status_badge.setFixedHeight(36)
        sidebar_layout.addWidget(self.status_badge)

        self.stack = QStackedWidget()

        self.page_home = self.build_home_page()
        self.page_settings = self.build_settings_page()
        self.page_logs = self.build_logs_page()

        self.stack.addWidget(self.page_home)
        self.stack.addWidget(self.page_settings)
        self.stack.addWidget(self.page_logs)

        content.addWidget(self.sidebar)
        content.addWidget(self.stack)

        container_layout.addWidget(self.titlebar)
        container_layout.addLayout(content)

        root.addWidget(self.container)

        self.switch_page(0)

    def build_home_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(18)

        title = QLabel("Home")
        title.setObjectName("pageTitle")

        card1 = QFrame()
        card1.setObjectName("card")
        card1_layout = QVBoxLayout(card1)
        card1_layout.setContentsMargins(20, 18, 20, 18)
        card1_layout.setSpacing(10)

        status_label = QLabel("현재 상태")
        status_label.setObjectName("cardTitle")
        self.current_status = QLabel("중지됨")
        self.current_status.setObjectName("cardValue")

        now_label = QLabel("현재 표시")
        now_label.setObjectName("cardTitle")
        self.current_now = QLabel("없음")
        self.current_now.setObjectName("cardValue")
        self.current_now.setWordWrap(True)

        card1_layout.addWidget(status_label)
        card1_layout.addWidget(self.current_status)
        card1_layout.addSpacing(8)
        card1_layout.addWidget(now_label)
        card1_layout.addWidget(self.current_now)

        button_row = QHBoxLayout()
        button_row.setSpacing(12)

        self.start_btn = AnimatedButton("실행")
        self.stop_btn = AnimatedButton("종료", "#DA373C", "#F04F54", "#B52D31")

        self.start_btn.clicked.connect(self.start_rpc)
        self.stop_btn.clicked.connect(self.stop_rpc)

        button_row.addWidget(self.start_btn)
        button_row.addWidget(self.stop_btn)

        card2 = QFrame()
        card2.setObjectName("card")
        card2_layout = QVBoxLayout(card2)
        card2_layout.setContentsMargins(20, 18, 20, 18)

        info = QLabel(
            "Chrome 창을 디스코드 활동상태에 표시합니다.\n"
            "\n"
            "ChromeCord v1.0.0 last update 26.03.31."
        )
        info.setObjectName("infoText")
        info.setWordWrap(True)
        card2_layout.addWidget(info)

        layout.addWidget(title)
        layout.addWidget(card1)
        layout.addLayout(button_row)
        layout.addWidget(card2)
        layout.addStretch()

        return page

    def build_settings_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(18)

        title = QLabel("Settings")
        title.setObjectName("pageTitle")

        card = QFrame()
        card.setObjectName("card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 18, 20, 18)
        card_layout.setSpacing(14)

        label = QLabel("표시 옵션")
        label.setObjectName("cardTitle")

        self.youtube_check = QCheckBox("유튜브 표시")
        self.google_check = QCheckBox("구글 표시")
        self.other_check = QCheckBox("기타 사이트 표시")
        self.keep_presence_check = QCheckBox("알트탭해도 마지막 활동 유지")

        self.save_btn = AnimatedButton("설정 저장", "#4E5058", "#6D6F78", "#3C3E45")
        self.save_btn.clicked.connect(self.save_settings)

        card_layout.addWidget(label)
        card_layout.addWidget(self.youtube_check)
        card_layout.addWidget(self.google_check)
        card_layout.addWidget(self.other_check)
        card_layout.addWidget(self.keep_presence_check)
        card_layout.addSpacing(8)
        card_layout.addWidget(self.save_btn)

        layout.addWidget(title)
        layout.addWidget(card)
        layout.addStretch()

        return page

    def build_logs_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(18)

        title = QLabel("Logs")
        title.setObjectName("pageTitle")

        card = QFrame()
        card.setObjectName("card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 18, 20, 18)

        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setObjectName("logBox")

        clear_btn = AnimatedButton("로그 지우기", "#4E5058", "#6D6F78", "#3C3E45")
        clear_btn.clicked.connect(self.log_box.clear)

        card_layout.addWidget(self.log_box)
        card_layout.addSpacing(8)
        card_layout.addWidget(clear_btn)

        layout.addWidget(title)
        layout.addWidget(card)
        layout.addStretch()

        return page

    def apply_styles(self):
        self.setStyleSheet("""
            QWidget {
                background: transparent;
                color: #F2F3F5;
                font-family: 'Segoe UI', 'Malgun Gothic';
                font-size: 14px;
            }
            QFrame#mainContainer {
                background: #313338;
                border: 0px solid #232428;
                border-radius: 20px;
            }
            QFrame#titlebar {
                background: #1E1F22;
                border-top-left-radius: 18px;
                border-top-right-radius: 18px;
                border-bottom: 1px solid #232428;
            }
            QLabel#windowTitle {
                color: #FFFFFF;
                font-size: 14px;
                font-weight: 600;
            }
            QPushButton#titleBtn, QPushButton#closeBtn {
                background: transparent;
                color: #B5BAC1;
                border: none;
                min-width: 34px;
                min-height: 28px;
                border-radius: 8px;
            }
            QPushButton#titleBtn:hover {
                background: #35373C;
                color: white;
            }
            QPushButton#closeBtn:hover {
                background: #ED4245;
                color: white;
            }
            QFrame#sidebar {
                background: #2B2D31;
                border-bottom-left-radius: 18px;
                border-right: 1px solid #232428;
            }
            QLabel#logo {
                background: #5865F2;
                color: white;
                border-radius: 27px;
                font-size: 24px;
                font-weight: 700;
            }
            QLabel#appName {
                color: white;
                font-size: 18px;
                font-weight: 700;
            }
            QLabel#appSub {
                color: #B5BAC1;
                font-size: 12px;
            }
            QLabel#statusBadge {
                border-radius: 10px;
                padding: 6px;
            }
            QCheckBox {
                spacing: 10px;
                color: #F2F3F5;
                font-size: 14px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
            }
            QCheckBox::indicator:unchecked {
                background: #1E1F22;
                border: 2px solid #80848E;
                border-radius: 5px;
            }
            QCheckBox::indicator:checked {
                background: #5865F2;
                border: 2px solid #5865F2;
                border-radius: 5px;
            }
            QTextEdit#logBox {
                background: #111214;
                border: 1px solid #232428;
                border-radius: 12px;
                color: #DBDEE1;
                padding: 10px;
                font-family: Consolas, 'Malgun Gothic';
            }
            QLabel#pageTitle {
                font-size: 28px;
                font-weight: 700;
                color: white;
            }
            QFrame#card {
                background: #1E1F22;
                border: 1px solid #232428;
                border-radius: 16px;
            }
            QLabel#cardTitle {
                color: #B5BAC1;
                font-size: 13px;
                font-weight: 600;
            }
            QLabel#cardValue {
                color: white;
                font-size: 18px;
                font-weight: 700;
            }
            QLabel#infoText {
                color: #DBDEE1;
                line-height: 1.5em;
            }
        """)

    def switch_page(self, index):
        self.stack.setCurrentIndex(index)

        page = self.stack.currentWidget()
        effect = QGraphicsOpacityEffect(page)
        page.setGraphicsEffect(effect)

        anim = QPropertyAnimation(effect, b"opacity", self)
        anim.setDuration(180)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        anim.start()

        self._anim = anim

        buttons = [self.home_btn, self.settings_btn, self.logs_btn]
        for i, btn in enumerate(buttons):
            btn.setChecked(i == index)
            if i == index:
                btn.setStyleSheet("""
                    QPushButton {
                        background: #404249;
                        color: white;
                        font-weight: 700;
                        border: none;
                        border-radius: 10px;
                        padding: 12px 14px;
                        text-align: left;
                    }
                """)
            else:
                btn.setStyleSheet("""
                    QPushButton {
                        background: transparent;
                        color: #B5BAC1;
                        font-weight: 600;
                        border: none;
                        border-radius: 10px;
                        padding: 12px 14px;
                        text-align: left;
                    }
                    QPushButton:hover {
                        background: #35373C;
                        color: white;
                    }
                """)

    def pulse(self, widget):
        geo = widget.geometry()
        bigger = geo.adjusted(-3, -3, 3, 3)

        anim = QPropertyAnimation(widget, b"geometry", self)
        anim.setDuration(160)
        anim.setKeyValueAt(0.0, geo)
        anim.setKeyValueAt(0.5, bigger)
        anim.setKeyValueAt(1.0, geo)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        anim.start()

        self._pulse = anim

    def load_config_to_ui(self):
        self.youtube_check.setChecked(config.get("show_youtube", True))
        self.google_check.setChecked(config.get("show_google", True))
        self.other_check.setChecked(config.get("show_other", True))
        self.keep_presence_check.setChecked(config.get("keep_presence_on_alt_tab", True))

    def save_settings(self):
        global config
        config = {
            "show_youtube": self.youtube_check.isChecked(),
            "show_google": self.google_check.isChecked(),
            "show_other": self.other_check.isChecked(),
            "keep_presence_on_alt_tab": self.keep_presence_check.isChecked()
        }
        save_config(config)
        QMessageBox.information(self, "Chromecord", "설정을 저장했습니다.")
        add_log("설정 저장 완료")

    def start_rpc(self):
        global running, worker_thread, config

        if running:
            QMessageBox.information(self, "Chromecord", "이미 실행 중입니다.")
            return

        config = load_config()
        self.load_config_to_ui()

        running = True
        worker_thread = threading.Thread(target=discord_loop, daemon=True)
        worker_thread.start()

        self.set_status("시작 중...", "#FEE75C")
        add_log("실행 버튼 클릭")

    def stop_rpc(self):
        global running
        if not running:
            QMessageBox.information(self, "Chromecord", "이미 중지되어 있어.")
            return

        running = False
        self.set_status("중지 중...", "#FEE75C")
        add_log("종료 버튼 클릭")

    def set_status(self, text, color):
        self.current_status.setText(text)
        self.current_status.setStyleSheet(
            f"color: {color}; font-size: 18px; font-weight: 700;"
        )
        self.status_badge.setText(text)
        self.status_badge.setStyleSheet(
            f"background: {color}; color: #111214; border-radius: 10px; font-weight: 700;"
        )
        self.pulse(self.status_badge)

    def set_now(self, text):
        self.current_now.setText(text)

    def append_log(self, text):
        self.log_box.append(text)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and event.position().y() <= 42:
            self.drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.drag_pos and event.buttons() & Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_pos)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self.drag_pos = None
        super().mouseReleaseEvent(event)

    def closeEvent(self, event):
        if self.is_quitting:
            event.accept()
            return

        event.ignore()
        self.hide()
        self.tray.showMessage(
            "Chromecord",
            "백그라운드에서 실행 중",
            QSystemTrayIcon.Information,
            2000
        )
        add_log("창을 닫고 트레이로 숨김")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 10))

    icon = QIcon(ICON_PATH) if os.path.exists(ICON_PATH) else QIcon()
    app.setWindowIcon(icon)

    window = ChromecordWindow()
    window.setWindowIcon(icon)
    window.show()
    window.fade.start()

    sys.exit(app.exec())