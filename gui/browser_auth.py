import os
import threading

from PySide6.QtCore import QStandardPaths, QThread, QTimer, QUrl, Signal, Slot, QObject
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile
from PySide6.QtWebEngineWidgets import QWebEngineView


BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)


class CaptchaAuthDialog(QDialog):
    """Small persistent browser used only when a site requires human verification."""

    def __init__(self, profile, url, parent=None):
        super().__init__(parent)
        self.profile = profile
        self.url = url
        self.cookies = None
        self._cookie_cache = {}

        self.setWindowTitle("SMI-DOWNLOADER - 사용자 인증")
        self.resize(1100, 760)

        layout = QVBoxLayout(self)

        info = QLabel(
            "이 사이트가 CAPTCHA / Cloudflare 인증을 요구합니다.\n"
            "아래 브라우저에서 직접 인증한 뒤 ‘인증 완료’를 눌러주세요."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        self.browser = QWebEngineView(self)
        self.page = QWebEnginePage(self.profile, self.browser)
        self.browser.setPage(self.page)
        self.browser.setUrl(QUrl(url))
        layout.addWidget(self.browser, 1)

        buttons = QHBoxLayout()
        buttons.addStretch(1)

        retry_button = QPushButton("새로고침")
        retry_button.clicked.connect(self.browser.reload)
        buttons.addWidget(retry_button)

        cancel_button = QPushButton("취소")
        cancel_button.clicked.connect(self.reject)
        buttons.addWidget(cancel_button)

        done_button = QPushButton("인증 완료")
        done_button.setDefault(True)
        done_button.clicked.connect(self._collect_cookies)
        buttons.addWidget(done_button)

        layout.addLayout(buttons)

    def _collect_cookies(self):
        self._cookie_cache = {}
        store = self.profile.cookieStore()

        try:
            store.cookieAdded.disconnect(self._on_cookie_added)
        except (RuntimeError, TypeError):
            pass

        store.cookieAdded.connect(self._on_cookie_added)
        store.loadAllCookies()

        # loadAllCookies() is asynchronous. Give Qt a short event-loop turn
        # so HttpOnly / persistent cookies are included as well.
        QTimer.singleShot(500, self._finish_cookie_collection)

    @Slot(object)
    def _on_cookie_added(self, cookie):
        try:
            name = bytes(cookie.name()).decode("utf-8", errors="replace")
            value = bytes(cookie.value()).decode("utf-8", errors="replace")
            domain = cookie.domain() or ""
            path = cookie.path() or "/"
            self._cookie_cache[(domain, path, name)] = {
                "name": name,
                "value": value,
                "domain": domain,
                "path": path,
            }
        except Exception:
            pass

    def _finish_cookie_collection(self):
        store = self.profile.cookieStore()
        try:
            store.cookieAdded.disconnect(self._on_cookie_added)
        except (RuntimeError, TypeError):
            pass

        self.cookies = list(self._cookie_cache.values())
        self.accept()


class BrowserAuthBridge(QObject):
    """Thread-safe bridge from downloader workers to a Qt browser dialog."""

    authRequested = Signal(str, object)

    def __init__(self, parent=None):
        super().__init__(parent)

        profile_dir = os.path.join(
            QStandardPaths.writableLocation(QStandardPaths.AppDataLocation),
            "browser-profile",
        )
        os.makedirs(profile_dir, exist_ok=True)

        self.profile = QWebEngineProfile("smi-captcha-auth", self)
        self.profile.setPersistentStoragePath(profile_dir)
        self.profile.setCachePath(os.path.join(profile_dir, "cache"))
        self.profile.setHttpUserAgent(BROWSER_USER_AGENT)
        self.profile.setPersistentCookiesPolicy(
            QWebEngineProfile.PersistentCookiesPolicy.ForcePersistentCookies
        )

        self.authRequested.connect(self._open_auth_dialog)

    def request_auth(self, url):
        # Normal downloads run in a Python worker thread. If this is ever
        # called on the GUI thread, avoid waiting on ourselves.
        if QThread.currentThread() == self.thread():
            return self._run_dialog(url)

        payload = {
            "event": threading.Event(),
            "cookies": None,
        }
        self.authRequested.emit(url, payload)
        payload["event"].wait()
        return payload["cookies"]

    @Slot(str, object)
    def _open_auth_dialog(self, url, payload):
        try:
            payload["cookies"] = self._run_dialog(url)
        finally:
            payload["event"].set()

    def _run_dialog(self, url):
        dialog = CaptchaAuthDialog(self.profile, url, self.parent())
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None

        if not dialog.cookies:
            QMessageBox.warning(
                self.parent(),
                "SMI-DOWNLOADER",
                "브라우저 인증 쿠키를 확인하지 못했습니다. 다시 시도해주세요.",
            )
            return None

        return dialog.cookies
