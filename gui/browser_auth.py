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
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile, QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView


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
            "아래 브라우저에서는 인증만 진행해주세요. 파일 다운로드는 차단됩니다.\n"
            "원래 사이트가 정상 표시되면 ‘인증 완료’를 눌러주세요."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        self.browser = QWebEngineView(self)
        self.page = QWebEnginePage(self.profile, self.browser)

        # Cloudflare Turnstile is sensitive to WebView capabilities and UA
        # consistency. Use QtWebEngine's real UA instead of spoofing another
        # Chrome version, and explicitly enable the browser features Turnstile
        # expects from embedded WebViews.
        settings = self.page.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalStorageEnabled, True)
        settings.setAttribute(
            QWebEngineSettings.WebAttribute.JavascriptCanOpenWindows,
            True,
        )

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
        self.profile.setHttpAcceptLanguage("ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7")

        # Keep QtWebEngine's native user agent. Spoofing a newer Chrome UA
        # while running an older embedded Chromium engine can cause Turnstile
        # to classify the browser as unsupported or inconsistent.
        self.profile.setPersistentCookiesPolicy(
            QWebEngineProfile.PersistentCookiesPolicy.ForcePersistentCookies
        )

        # Drop stale challenge resources while preserving persistent cookies.
        # This avoids reusing a cached Turnstile error page after an app update.
        self.profile.clearHttpCache()

        # 인증창은 쿠키를 얻는 용도만 사용합니다. 사이트가 CAPTCHA 통과
        # 직후 자동 다운로드를 시도해도 브라우저가 파일을 저장하지 않도록
        # 모든 WebEngine 다운로드 요청을 취소합니다.
        self.profile.downloadRequested.connect(self._cancel_download)

        self.authRequested.connect(self._open_auth_dialog)

    @Slot(object)
    def _cancel_download(self, download):
        try:
            download.cancel()
        except Exception:
            pass

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

        return {
            "cookies": dialog.cookies,
            "user_agent": self.profile.httpUserAgent(),
        }
