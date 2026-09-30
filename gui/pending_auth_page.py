import threading

from PySide6.QtCore import Qt, Signal, QObject
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from kudong import (
    get_pending_auth_items,
    progress_callback,
    queue_all_pending_auth_retries,
    queue_pending_auth_retry,
    remove_pending_auth_item,
    reset_pending_auth_runtime_statuses,
    retry_all_pending_auth_items,
    retry_pending_auth_item,
    set_pending_auth_changed_provider,
)

class PendingMenuButton(QPushButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("btn_pending")
        self.setMinimumSize(0, 45)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.setText("보류목록")
        self.setStyleSheet(
            "background-image: url(:/icons/images/icons/cil-bell.png);"
        )

        self.badge = QLabel(self)
        self.badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.badge.setMinimumSize(20, 20)
        self.badge.setMaximumHeight(20)
        self.badge.setStyleSheet(
            "QLabel {"
            " background-color: #e5484d;"
            " color: white;"
            " border-radius: 10px;"
            " padding-left: 5px;"
            " padding-right: 5px;"
            " font-weight: 700;"
            " font-size: 11px;"
            "}"
        )
        self.badge.hide()

    def set_count(self, count):
        if count <= 0:
            self.badge.hide()
            return
        self.badge.setText("99+" if count > 99 else str(count))
        self.badge.adjustSize()
        width = max(20, self.badge.width())
        self.badge.resize(width, 20)
        self.badge.show()
        self._place_badge()

    def _place_badge(self):
        margin = 7
        self.badge.move(max(2, self.width() - self.badge.width() - margin), 5)
        self.badge.raise_()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._place_badge()


class PendingAuthPage(QObject):
    pendingChanged = Signal()
    retryFinished = Signal(str)
    batchFinished = Signal(str)

    def __init__(self, MainWindow, widgets):
        super().__init__(MainWindow)
        self.MainWindow = MainWindow
        self.widgets = widgets
        self._batch_running = False
        reset_pending_auth_runtime_statuses()
        self._build_menu_button()
        self._build_page()

        self.pendingChanged.connect(self.refresh)
        self.retryFinished.connect(self._on_retry_finished)
        self.batchFinished.connect(self._on_batch_finished)
        set_pending_auth_changed_provider(self.pendingChanged.emit)

        self.refresh()

    def _build_menu_button(self):
        self.menu_button = PendingMenuButton(self.widgets.topMenu)
        self.widgets.btn_pending = self.menu_button

        insert_at = self.widgets.verticalLayout_8.indexOf(self.widgets.btn_log)
        if insert_at < 0:
            self.widgets.verticalLayout_8.addWidget(self.menu_button)
        else:
            self.widgets.verticalLayout_8.insertWidget(insert_at, self.menu_button)

        self.menu_button.clicked.connect(self.open_page)

    def _build_page(self):
        self.page = QWidget()
        self.page.setObjectName("pending_auth_page")
        root = QVBoxLayout(self.page)
        root.setContentsMargins(24, 22, 24, 22)
        root.setSpacing(14)

        title = QLabel("보류목록")
        title.setStyleSheet("font-size: 22px; font-weight: 700;")
        root.addWidget(title)

        desc = QLabel(
            "CAPTCHA / Cloudflare 인증이 필요한 항목입니다. "
            "자동 다운로드 중에는 창을 띄우지 않고 여기에 모아둡니다. "
            "‘전체 처리 시작’을 누르면 현재 작업 종료 후 순서대로 인증/다운로드합니다."
        )
        desc.setWordWrap(True)
        root.addWidget(desc)

        self.summary = QLabel("")
        self.summary.setStyleSheet("font-weight: 600;")
        root.addWidget(self.summary)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["상태", "작품", "회차", "제작자", "사유", "URL"]
        )
        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)

        root.addWidget(self.table, 1)

        button_row = QHBoxLayout()

        self.batch_button = QPushButton("전체 처리 시작")
        self.batch_button.setMinimumHeight(38)
        self.batch_button.clicked.connect(self.retry_all)
        button_row.addWidget(self.batch_button)

        self.retry_button = QPushButton("선택 항목 처리")
        self.retry_button.setMinimumHeight(38)
        self.retry_button.clicked.connect(self.retry_selected)
        button_row.addWidget(self.retry_button)

        self.remove_button = QPushButton("목록에서 제거")
        self.remove_button.setMinimumHeight(38)
        self.remove_button.clicked.connect(self.remove_selected)
        button_row.addWidget(self.remove_button)

        refresh_button = QPushButton("새로고침")
        refresh_button.setMinimumHeight(38)
        refresh_button.clicked.connect(self.refresh)
        button_row.addWidget(refresh_button)

        button_row.addStretch(1)
        root.addLayout(button_row)

        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        root.addWidget(self.status_label)

        self.widgets.stackedWidget.addWidget(self.page)

    def open_page(self):
        self.refresh()
        self.widgets.stackedWidget.setCurrentWidget(self.page)

        # Import lazily here. A module-level UIFunctions import creates a
        # gui <-> modules startup cycle, but at click time initialization is
        # already complete and the normal menu selection styling is safe.
        from modules.ui_functions import UIFunctions

        UIFunctions.resetStyle(self.MainWindow, "btn_pending")
        self.menu_button.setStyleSheet(
            UIFunctions.selectMenu(self.menu_button.styleSheet())
        )

    def _status_text(self, value):
        return {
            "pending": "보류",
            "queued": "다음 차례 대기",
            "authenticating": "인증/재시도 중",
        }.get(value or "", value or "보류")

    def refresh(self):
        items = get_pending_auth_items()
        self.menu_button.set_count(len(items))
        self.summary.setText("현재 보류 항목: %d개" % len(items))

        self.table.setRowCount(len(items))
        for row, item in enumerate(items):
            values = [
                self._status_text(item.get("status")),
                item.get("animeName", ""),
                (str(item.get("episode", "")) + "화")
                if str(item.get("episode", ""))
                else "",
                item.get("creator", ""),
                item.get("reason", ""),
                item.get("website", ""),
            ]
            for col, value in enumerate(values):
                cell = QTableWidgetItem(str(value))
                cell.setToolTip(str(value))
                if col == 0:
                    cell.setData(Qt.ItemDataRole.UserRole, item.get("id"))
                    cell.setData(
                        Qt.ItemDataRole.UserRole + 1,
                        item.get("status", "pending"),
                    )
                self.table.setItem(row, col, cell)

        if items and self.table.currentRow() < 0:
            self.table.selectRow(0)

    def _selected(self):
        row = self.table.currentRow()
        if row < 0:
            return None, None

        first = self.table.item(row, 0)
        if first is None:
            return None, None

        return (
            first.data(Qt.ItemDataRole.UserRole),
            first.data(Qt.ItemDataRole.UserRole + 1),
        )

    def retry_all(self):
        if self._batch_running:
            QMessageBox.information(
                self.MainWindow,
                "SMI-DOWNLOADER",
                "보류목록 전체 처리가 이미 예약되어 있습니다.",
            )
            return

        items = get_pending_auth_items()
        if not items:
            QMessageBox.information(
                self.MainWindow,
                "SMI-DOWNLOADER",
                "처리할 보류 항목이 없습니다.",
            )
            return

        if any(
            item.get("status") in ("queued", "authenticating")
            for item in items
        ):
            QMessageBox.information(
                self.MainWindow,
                "SMI-DOWNLOADER",
                "이미 재시도 대기 또는 인증 중인 항목이 있습니다.",
            )
            return

        count = queue_all_pending_auth_retries()
        if count <= 0:
            self.refresh()
            return

        self._batch_running = True
        self.batch_button.setEnabled(False)
        self.retry_button.setEnabled(False)
        self.status_label.setText(
            f"보류 {count}개 전체 처리를 예약했습니다. "
            "현재 전체 다운로드가 진행 중이면 끝난 뒤 순서대로 처리합니다. "
            "같은 사이트의 인증 쿠키는 가능한 동안 재사용합니다."
        )
        self.refresh()

        worker = threading.Thread(
            target=self._batch_worker,
            daemon=True,
        )
        worker.start()

    def _batch_worker(self):
        result = retry_all_pending_auth_items(progress_callback)
        message = (
            "보류 전체 처리 완료 - "
            f"성공 {result.get('success', 0)}개, "
            f"실패 {result.get('failed', 0)}개, "
            f"남음 {result.get('remaining', 0)}개"
        )
        if result.get("cancelled"):
            message += " (사용자 인증 취소)"
        self.batchFinished.emit(message)

    def _on_batch_finished(self, message):
        self._batch_running = False
        self.batch_button.setEnabled(True)
        self.retry_button.setEnabled(True)
        self.status_label.setText(message)
        self.refresh()

    def retry_selected(self):
        item_id, status = self._selected()
        if not item_id:
            QMessageBox.information(
                self.MainWindow,
                "SMI-DOWNLOADER",
                "재시도할 보류 항목을 선택해주세요.",
            )
            return

        if status in ("queued", "authenticating"):
            QMessageBox.information(
                self.MainWindow,
                "SMI-DOWNLOADER",
                "이미 다음 차례로 예약된 항목입니다.",
            )
            return

        if not queue_pending_auth_retry(item_id):
            self.refresh()
            return

        self.status_label.setText(
            "다음 차례로 예약했습니다. 현재 다운로드가 진행 중이면 "
            "그 작업이 끝난 뒤 인증창이 열립니다."
        )
        self.refresh()

        worker = threading.Thread(
            target=self._retry_worker,
            args=(item_id,),
            daemon=True,
        )
        worker.start()

    def _retry_worker(self, item_id):
        ok = retry_pending_auth_item(item_id, progress_callback)
        self.retryFinished.emit(
            "보류 항목 다운로드가 완료되었습니다."
            if ok
            else "보류 항목 재시도가 끝났습니다. 실패했다면 목록에 그대로 남습니다."
        )

    def _on_retry_finished(self, message):
        self.status_label.setText(message)
        self.refresh()

    def remove_selected(self):
        item_id, status = self._selected()
        if not item_id:
            return

        if status in ("queued", "authenticating"):
            QMessageBox.information(
                self.MainWindow,
                "SMI-DOWNLOADER",
                "예약 또는 인증 중인 항목은 완료 후 제거해주세요.",
            )
            return

        answer = QMessageBox.question(
            self.MainWindow,
            "SMI-DOWNLOADER",
            "선택한 보류 항목을 목록에서 제거할까요?\n"
            "다운로드 파일이나 finish.txt는 건드리지 않습니다.",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        remove_pending_auth_item(item_id)
        self.refresh()

