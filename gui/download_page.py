
from datetime import datetime
from functools import partial
from PySide6.QtCore import *
from PySide6.QtGui import *
from PySide6.QtWidgets import *
from kudong import *
from modules.font_config import fs, pt

clickedRemoveRow = -1;
isScheduler_button_clicked = False;

class AllFavoritesWorker(QThread):
    progress = Signal(int, int)
    completed = Signal(object)
    failed = Signal(str)

    def run(self):
        try:
            result = requestSearchAnimeInfo("", 0)
            if result is None:
                raise RuntimeError("애니시아 작품 목록을 가져오지 못했습니다.")

            search_list, page_info = result
            if search_list is None or page_info is None:
                raise RuntimeError("애니시아 작품 목록을 가져오지 못했습니다.")

            collected = []
            seen = set()

            def append_page(items):
                for anime in items:
                    anime_no = str(anime.animeNo)
                    if anime_no in seen:
                        continue
                    seen.add(anime_no)
                    collected.append({
                        "Anime": anime.subject.replace('"', ''),
                        "AnimeNo": anime_no
                    })

            append_page(search_list)

            total_pages = max(int(page_info.totalPages), 1)
            self.progress.emit(1, total_pages)

            for page in range(1, total_pages):
                result = requestSearchAnimeInfo("", page)
                if result is None:
                    raise RuntimeError(f"애니시아 작품 목록 {page + 1}페이지를 가져오지 못했습니다.")

                search_list, _ = result
                if search_list is None:
                    raise RuntimeError(f"애니시아 작품 목록 {page + 1}페이지를 가져오지 못했습니다.")

                append_page(search_list)
                self.progress.emit(page + 1, total_pages)

            self.completed.emit(collected)

        except Exception as e:
            self.failed.emit(str(e))
 
# 2. Download_Page
# ///////////////////////////////////////////////////////////////
class DownloadPage:

    def __init__(self, MainWindow, widgets):
        self.MainWindow = MainWindow
        self.widgets = widgets    

        self.widgets.scheduler_table.horizontalHeader().setSectionResizeMode(0,QHeaderView.Fixed)
        self.widgets.scheduler_table.horizontalHeader().setSectionResizeMode(1,QHeaderView.Stretch)
        self.widgets.scheduler_table.setColumnWidth(0, 200)
        self.widgets.scheduler_table.setColumnWidth(1, 400)
        self.widgets.scheduler_table.verticalHeader().setSectionsMovable(False)
        self.widgets.scheduler_table.cellClicked.connect(self.on_scheduler_cell_clicked)
        self.widgets.scheduler_table.setFocusPolicy(Qt.NoFocus)

        self.widgets.yml_save_button.clicked.connect(self.onYmlsaveButtonClicked)
        self.widgets.yml_reset_button.clicked.connect(self.onYmlresetButtonClicked)
        self.widgets.yml_open_button.clicked.connect(self.onYmlopenButtonClicked)
        self.widgets.yml_reload_button.clicked.connect(self.onYmlreloadButtonClicked)
        self.widgets.yml_remove_row.clicked.connect(self.onYmlremoveRowButtonClicked)

        # 애니시아 전체 작품을 즐겨찾기에 일괄 추가합니다.
        # UI 생성 파일(main.ui / ui_main_*.py)을 직접 수정하지 않고,
        # 다운로드 관리 버튼 행의 비어 있는 4번 컬럼에 런타임으로 추가합니다.
        self.widgets.yml_all_favorites_button = QPushButton(self.widgets.row_2)
        self.widgets.yml_all_favorites_button.setObjectName("yml_all_favorites_button")
        self.widgets.yml_all_favorites_button.setMinimumSize(QSize(110, 0))
        self.widgets.yml_all_favorites_button.setStyleSheet(
            self.widgets.yml_reset_button.styleSheet()
        )
        self.widgets.yml_all_favorites_button.setText("전체 즐겨찾기")
        self.widgets.gridLayout_2.addWidget(
            self.widgets.yml_all_favorites_button, 1, 4, 1, 1
        )
        self.widgets.yml_all_favorites_button.clicked.connect(
            self.onAllFavoritesButtonClicked
        )
        self.all_favorites_worker = None

        common.downloadPage_instance = self # left_toggle_bar에서 Yml save 참조용

        with open('anime.yml', 'r', encoding='utf-8') as file:
            data = yaml.safe_load(file)

        self.widgets.yml_downloadPath.setText(get_global_outpath())
        self.widgets.yml_downloadPath.setReadOnly(True)
        self.widgets.ym_openfileButton.clicked.connect(self.on_openfile_clicked)

        self.widgets.yml_content.setPlainText(
            "anime_list: '" + data['anime_list'] + "'\n"  + 
            "download_path: '" + data['download_path'] + "'"
        );
        self.widgets.yml_content.setReadOnly(True)

        animelist = json.loads(data['anime_list'])

        count = 0
        for k in animelist:
            self.widgets.scheduler_table.setItem(count,0,QTableWidgetItem(str(k['AnimeNo'])));
            self.widgets.scheduler_table.setItem(count,1,QTableWidgetItem(k['Anime']));
            count += 1

        self.widgets.scheduler_table.setRowCount(count + 10)    
        self.widgets.scheduler_table.horizontalHeader().setVisible(True)
        self.widgets.scheduler_table.verticalHeader().setSectionsMovable(False)

        self.widgets.scheduler_folder.clicked.connect(self.onDownloadFolderButtonClicked)
        self.widgets.scheduler_table.cellClicked.connect(self.onYmlremoveRowClicked)

        self.widgets.scheduler_comboBox.setEnabled(False)
        self.widgets.scheduler_comboBox.setCurrentIndex(7);
        # self.widgets.scheduler_comboBox.setStyleSheet("""
        #     QComboBox:disabled {
        #         background-color: lightgray;
        #         color: gray;
        #     }
        # """)

        self.widgets.scheduler_checkBox.stateChanged.connect(self.scheduler_checkbox_changed)
        self.widgets.scheduler_button.clicked.connect(self.scheduler_button_clicked)

        self.timer = QTimer(self.MainWindow)
        self.timer.timeout.connect(self.scheduler_update)

    #테이블을 클릭했을떄
    def on_scheduler_cell_clicked(self, row, column):
        #print(f"Row {row} {column}")
        item = self.widgets.scheduler_table.item(row, 0) # AnimeNo 가 None이 아닌지 체크
        if item is None or item.text() == "":
            return

        anime, subs = requestAnimeInfo(item.text());
        common.show_anime_detail(self, anime, subs)

    # 다운로드 경로 선택시
    def on_openfile_clicked(self):
        #fileDir = QFileDialog.getOpenFileName(self);
        #self.widgets.yml_downloadPath.setText(outpath)
        fileDir = QFileDialog.getExistingDirectory(self.MainWindow,'폴더선택','')
        if(fileDir != ""):
            self.widgets.yml_downloadPath.setText(fileDir)
            set_global_outpath(fileDir)

            with open('settings.yml', encoding='UTF8') as f:
                config = yaml.load(f, Loader=yaml.FullLoader)
                config['auto-download-path'] = False;
            
            with open('settings.yml', 'w', encoding='utf-8') as f:
                yaml.safe_dump(config, f, allow_unicode=True)

            with open('anime.yml', 'r', encoding='utf-8') as file:
                data = yaml.safe_load(file)
                #print(data)
                data['download_path'] = fileDir + "/"

            with open('anime.yml', 'w', encoding='utf-8') as file:
                yaml.safe_dump(data, file, allow_unicode=True)

            self.widgets.yml_content.setPlainText(
                "anime_list: '" + data['anime_list'] + "'\n"  + 
                "download_path: '" + data['download_path'] + "'"
            );
    
    def onAllFavoritesButtonClicked(self):
        if self.all_favorites_worker is not None and self.all_favorites_worker.isRunning():
            return

        reply = QMessageBox.question(
            self.MainWindow,
            "SMI-DOWNLOADER",
            "애니시아에 등록된 전체 작품을 즐겨찾기에 추가할까요?\n"
            "기존 즐겨찾기는 유지되고, AnimeNo가 같은 작품은 중복 추가되지 않습니다.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        self.widgets.yml_all_favorites_button.setEnabled(False)
        self.widgets.yml_all_favorites_button.setText("목록 확인 중...")

        self.all_favorites_worker = AllFavoritesWorker(self.MainWindow)
        self.all_favorites_worker.progress.connect(self.onAllFavoritesProgress)
        self.all_favorites_worker.completed.connect(self.onAllFavoritesCompleted)
        self.all_favorites_worker.failed.connect(self.onAllFavoritesFailed)
        self.all_favorites_worker.finished.connect(self.onAllFavoritesWorkerFinished)
        self.all_favorites_worker.start()

    @Slot(int, int)
    def onAllFavoritesProgress(self, current_page, total_pages):
        self.widgets.yml_all_favorites_button.setText(
            f"전체 수집 {current_page}/{total_pages}"
        )

    @Slot(object)
    def onAllFavoritesCompleted(self, all_anime):
        try:
            with open('anime.yml', 'r', encoding='utf-8') as file:
                data = yaml.safe_load(file)

            try:
                current_list = json.loads(data.get('anime_list', '[]'))
            except Exception:
                current_list = []

            existing_ids = {
                str(item.get('AnimeNo'))
                for item in current_list
                if item.get('AnimeNo') is not None
            }

            added = 0
            for item in all_anime:
                anime_no = str(item['AnimeNo'])
                if anime_no in existing_ids:
                    continue
                current_list.append(item)
                existing_ids.add(anime_no)
                added += 1

            data['anime_list'] = json.dumps(
                current_list,
                ensure_ascii=False,
                indent=2
            )

            with open('anime.yml', 'w', encoding='utf-8') as file:
                yaml.safe_dump(data, file, allow_unicode=True)

            # reload 함수가 새 행을 만들지는 않으므로 먼저 충분한 행 수를 확보합니다.
            self.widgets.scheduler_table.setRowCount(len(current_list) + 10)
            self.onYmlreloadButtonClicked()

            QMessageBox.information(
                self.MainWindow,
                "SMI-DOWNLOADER",
                f"전체 작품 {len(all_anime)}개를 확인했습니다.\n"
                f"새로 추가: {added}개\n"
                f"기존/중복 제외: {len(all_anime) - added}개"
            )

        except Exception as e:
            QMessageBox.critical(
                self.MainWindow,
                "SMI-DOWNLOADER",
                "전체 즐겨찾기 저장 중 오류가 발생했습니다.\n" + str(e)
            )

    @Slot(str)
    def onAllFavoritesFailed(self, message):
        QMessageBox.critical(
            self.MainWindow,
            "SMI-DOWNLOADER",
            "전체 작품 목록을 가져오지 못했습니다.\n" + message
        )

    @Slot()
    def onAllFavoritesWorkerFinished(self):
        self.widgets.yml_all_favorites_button.setEnabled(True)
        self.widgets.yml_all_favorites_button.setText("전체 즐겨찾기")

    # Anime.yml에 내용을 저장합니다.
    def onYmlsaveButtonClicked(self):
        temp = ""

        save_dict = {}
        count = 0

        for row in range(self.widgets.scheduler_table.rowCount()):
            id = self.widgets.scheduler_table.item(row, 0)
            anime = self.widgets.scheduler_table.item(row, 1)
            if(id is None or anime is None):
                continue;
            save_dict[id.text()] = anime.text();
            count += 1

        for key,value in save_dict.items():
            id = key
            anime = value
            #print(str(row) + " " + str(self.widgets.scheduler_table.rowCount()))
            temp += "{ \"Anime\":\""+anime+"\", \"AnimeNo\":\""+str(id)+"\" }"
            temp += ",\n"

        temp = temp[:-2] +"\n"
        temp = '[\n' +temp + ']'

        self.widgets.scheduler_table.setRowCount(count + 10)

        with open('anime.yml', 'r', encoding='utf-8') as file:
            data = yaml.safe_load(file)
            data['anime_list'] = temp

        with open('anime.yml', 'w', encoding='utf-8') as file:
            yaml.safe_dump(data, file, allow_unicode=True)

        self.widgets.yml_content.setPlainText(
            "anime_list: '" + data['anime_list'] + "'\n"  + 
            "download_path: '" + data['download_path'] + "'"
        );
    
        self.onYmlreloadButtonClicked() # 세이브 후 테이블 리로드

    def onYmlopenButtonClicked(self):
        webbrowser.open(os.path.abspath('.') + "/anime.yml")             

    def onYmlremoveRowClicked(self, row,column):
        global clickedRemoveRow
        clickedRemoveRow = row

    def onYmlremoveRowButtonClicked(self):
        self.widgets.scheduler_table.removeRow(clickedRemoveRow)
        rowCount = self.widgets.scheduler_table.rowCount()
        self.widgets.scheduler_table.insertRow(rowCount)

    def onYmlreloadButtonClicked(self):

        with open('anime.yml', 'r', encoding='utf-8') as file:
            data = yaml.safe_load(file)

        self.widgets.yml_content.setPlainText(
            "anime_list: '" + data['anime_list'] + "'\n"  + 
            "download_path: '" + data['download_path'] + "'"
        );

        self.widgets.yml_downloadPath.setText(data['download_path'])
        set_global_outpath(data['download_path'])

        #테이블 모든 데이터 삭제
        self.widgets.scheduler_table.clearContents()

        animelist = json.loads(data['anime_list'])

        count = 0
        for k in animelist:
            self.widgets.scheduler_table.setItem(count,0,QTableWidgetItem(str(k['AnimeNo'])));
            self.widgets.scheduler_table.setItem(count,1,QTableWidgetItem(k['Anime']));
            count += 1

    def onYmlresetButtonClicked(self):
        self.widgets.scheduler_table.clearContents()
        # self.widgets.yml_content.setPlainText(
        #     "anime_list: '[\n\n]'\n"  + 
        #     "download_path: '" + os.path.abspath('.') + "'"
        # );

    def onDownloadFolderButtonClicked(self):
        import platform, subprocess
        path = get_global_outpath()
        if platform.system() == 'Darwin':
            subprocess.Popen(['open', path])
        elif platform.system() == 'Windows':
            os.startfile(path)
        else:
            subprocess.Popen(['xdg-open', path])

    # 스케줄러 체크박스 클릭시
    def scheduler_checkbox_changed(self,state):
        if state == 2: #checked
            self.widgets.scheduler_comboBox.setEnabled(True)
            self.widgets.scheduler_comboBox.setCurrentIndex(0);
            self.widgets.scheduler_button.setText("스케줄러 시작")
        else:
            self.widgets.scheduler_comboBox.setEnabled(False)
            self.widgets.scheduler_comboBox.setCurrentIndex(7);
            self.widgets.scheduler_button.setText("다운로드 시작")

    # 스케줄러 시작 버튼 클릭시
    def scheduler_button_clicked(self):
        global isScheduler_button_clicked
        if isScheduler_button_clicked == False: # 시작 로직

            # 이전 실행에서 남은 중지 신호를 초기화합니다.
            set_global_quitSignal(False)

            idx = self.widgets.scheduler_comboBox.currentIndex()

            #"반복 없음"이 스케쥴러 모드에서 버튼 클릭 되었을때 처리
            if self.widgets.scheduler_checkBox.isChecked() and idx == 7: 
                QMessageBox.information( 
                self.MainWindow, 
                "SMI-DOWNLOADER", 
                "반복 없음은 선택할수 없습니다!");
                return

            if self.widgets.scheduler_checkBox.isChecked():
                self.widgets.left_progressName.setText("곧 스케쥴러가 시작됩니다...")
                self.widgets.left_progressName.setWordWrap(True)
            else:
                self.widgets.left_progressName.setText("곧 다운로드가 시작됩니다...")
                self.widgets.left_progressName.setWordWrap(True)

            if lock_Scheduler() == True:
                thread = threading.Thread(target= lambda: requestMultipleAnimeSMI(progress_callback))
                thread.start()
            else:
                QMessageBox.information( 
                self.MainWindow, 
                "SMI-DOWNLOADER", 
                "다른 작업이 먼저 수행중입니다....");
                return
            
            afterSheet = "background-color: rgb(156, 179, 199); color: rgb(255, 255, 255); font-size: " + str(fs(10, 16)) + "px;"
            self.widgets.scheduler_button.setStyleSheet(afterSheet)

            self.widgets.scheduler_checkBox.setEnabled(False)

            if self.widgets.scheduler_comboBox.isEnabled():
                self.widgets.scheduler_button.setText("스케줄러 중지")
                common.isScheduler_mode = True;
            else:
                self.widgets.scheduler_button.setText("다운로드 중지")
                common.isScheduler_mode = False;
            
            self.widgets.scheduler_comboBox.setEnabled(False)
            isScheduler_button_clicked = True

            if self.widgets.scheduler_checkBox.isChecked(): # 반복 옵션이 체크 되어있었다면

                min = 1000 * 60
                hour = min * 60
                day = hour * 24

                if idx == 0: #10분마다
                    self.timer.start(10 * min)
                elif idx == 1: #30분마다
                    self.timer.start(30 * min)
                elif idx == 2: #1시간마다
                    self.timer.start(hour)
                elif idx == 3: #3시간마다
                    self.timer.start(3 * hour)
                elif idx == 4: #6시간마다
                    self.timer.start(6 * hour)
                elif idx == 5: #12시간마다
                    self.timer.start(12 * hour)
                elif idx == 6: #24시간마다
                    self.timer.start(day)
                    
        else: # 중지 로직
            # 현재 네트워크 요청이 timeout으로 풀리면 다음 작품으로 넘어가지 않습니다.
            set_global_quitSignal(True)
            self.widgets.left_progressName.setText("다운로드 중지 요청됨...")
            self.widgets.left_progressName.setWordWrap(True)

            beforeSheet = "background-color: rgb(52, 59, 72); font-size: " + str(fs(10, 16)) + "px;"
            self.widgets.scheduler_button.setStyleSheet(beforeSheet)
            
            self.widgets.scheduler_checkBox.setEnabled(True)

            if common.isScheduler_mode == True:
                self.widgets.scheduler_button.setText("스케줄러 시작") 
                self.widgets.scheduler_comboBox.setEnabled(True)
                self.timer.stop()
            else:
                self.widgets.scheduler_button.setText("다운로드 시작")
                self.widgets.scheduler_comboBox.setEnabled(False)

            isScheduler_button_clicked = False
            
    # 타이머
    def scheduler_update(self):
        self.widgets.left_progressName.setText("곧 스케쥴러가 시작됩니다...")
        self.widgets.left_progressName.setWordWrap(True)
        if lock_Scheduler() == True:
            thread = threading.Thread(target= lambda: requestMultipleAnimeSMI(progress_callback))
            thread.start()


