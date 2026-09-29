import requests
import json
import sys
import re
import os
import yaml
import traceback
import threading
import natsort
import gdrive
import urllib.error
import urllib.parse
from http import client
from urllib import request
from urllib.request import urlopen
from urllib.parse import unquote
from urllib.parse import quote
from urllib.parse import urlparse
from urllib.parse import urljoin
from datetime import datetime
from bs4 import BeautifulSoup
from kudong.winpng import extract_winpng_files

#pip install gdown
#pip install requests
#pip install PyYAML
#pip install beautifulsoup4

#시놀로지(헤놀로지)
# wget https://bootstrap.pypa.io/get-pip.py
# python3 get-pip.py
# python3 -m pip install {package name}
# python3 -m pip install 'urllib3<2.0'
# python3 -m pip install gdown

# =================================================
# Title: SMI AUTO DOWNLOADER
# Author: KUDONG
# Version: 1.5.8
# Url: https://github.com/dhku/SMI-Auto-Downloader
# =================================================

AnimeNO = -1
AnimeName = "None"
outpath = ""
smiDir = ""
isDownloadError = 0

download_progress_count = 0;
download_progress_length = 0;

console_output = ""
log_path = ""

p_extension = re.compile(r"^.*\.(zip|ass|smi|7z)$", re.IGNORECASE)
regrex1 = re.compile(r".*(naver).*")
regrex2 = re.compile(r".*(blogspot).*")
regrex3 = re.compile(r".*(tistory).*")

p_google = re.compile(r"(.*(https://drive.google.com/file/d/).*)")
p_google_2_1 = re.compile(r"(.*(https://docs.google.com/uc).*)")
p_google_2_2 = re.compile(r"(.*(https://drive.google.com/uc).*)")
p_google_3 = re.compile(r"(.*(https://drive.usercontent.google.com/download).*)")

thread_lock = threading.Lock()
isRunning = False
quitSignal = False

REQUEST_TIMEOUT = 10
DOWNLOAD_TIMEOUT = 20

# GUI가 제공하는 수동 CAPTCHA 인증 함수. CLI/비-GUI 환경에서는 None입니다.
browser_auth_provider = None

def set_browser_auth_provider(provider):
    global browser_auth_provider
    browser_auth_provider = provider

def init_paths(autoPath):
    global outpath, log_path
    log_path = os.path.abspath('.') + "/log/"

    with open('anime.yml', 'r', encoding='utf-8') as file:
        data = yaml.safe_load(file)

    if(data['download_path'] != ""):
        outpath = data['download_path']
    else:
        outpath = os.path.abspath('.') + "/downloads/"

    if(autoPath is True):
        outpath = os.path.abspath('.') + "/downloads/"        

    if not os.path.exists(outpath):
        os.makedirs(outpath)

    data['download_path'] = outpath
    with open('anime.yml', 'w', encoding='utf-8') as file:
        yaml.safe_dump(data, file, allow_unicode=True)

def download(url, file_name = None):
    with open(file_name, "wb") as file:  
        response = requests.get(url, timeout=DOWNLOAD_TIMEOUT)
        response.raise_for_status()
        file.write(response.content)

def text_to_file(txt, file_name):
    f = open(file_name, 'w',encoding="UTF-8")
    f.write(txt)
    f.close()

def set_global_outpath(path):
    global outpath
    outpath = path + "/"

def set_global_quitSignal(signal):
    global quitSignal
    quitSignal = signal

def get_global_outpath():
    return outpath

def get_global_console_output():
    global console_output
    return console_output

def get_new_log_file():
    now = datetime.now()
    formatted_date = now.strftime("%Y-%m-%d")
    new_filename = ""
    log_file_list = natsort.natsorted(os.listdir(os.path.abspath('.') + "/log"))
    log_file_list.remove("error.log")

    if(len(log_file_list) != 0):
        latest_file = log_file_list[len(log_file_list) - 1]
        pattern = r"(\d{4}-\d{2}-\d{2})-(\d+)\.log"
        match = re.match(pattern, latest_file)
        if match and match.group(1) == formatted_date:
            date = match.group(1)
            counter = int(match.group(2)) + 1
            temp = f"{date}-{counter}.log"
            if not os.path.exists(log_path + temp):
                new_filename = temp
        else:
            counter = 1
            while True:
                temp = f"{formatted_date}-{counter}.log"
                if not os.path.exists(log_path + temp):
                    new_filename = temp
                    break
                counter += 1
    else:
        counter = 1
        while True:
            temp = f"{formatted_date}-{counter}.log"
            if not os.path.exists(log_path + temp):
                new_filename = temp
                break
            counter += 1
    return new_filename

def get_download_progress_length(json_data):
    global AnimeName
    #다운로드 사이즈 체크
    download_progress_length = 0
    for k in json_data:

        name = k['name']
        episode = k['episode']
        updDt = k['updDt']
        website = unquote(k['website'])

        folder_name = AnimeName
        folder_name = folder_name.replace(":","")
        folder_name = folder_name.replace("/","")
        folder_name = folder_name.replace("?","")
        folder_name = folder_name.replace("<","")
        folder_name = folder_name.replace(">","")
        folder_name = folder_name.replace("*","")
        folder_name = folder_name.replace("|","")
        smiDir = folder_name + "/" + episode + "화/" + name + "/"

        if os.path.isfile(outpath + smiDir + "finish.txt"):
            continue;
        if regrex1.match(website):
            download_progress_length += download_count_naver(website)
        elif regrex2.match(website):
            download_progress_length += download_count_blogspot(website)
        elif regrex3.match(website):
            download_progress_length += download_count_tistory(website)
        elif website == "":
            continue;
        else:
            download_progress_length += download_count_website(website)
    return download_progress_length

def lock_Scheduler():
    global isRunning
    thread_lock.acquire()
    if isRunning == False:
        isRunning = True
        thread_lock.release()
        return True
    else:
        thread_lock.release()
        return False

def unlock_Scheduler():
    global isRunning
    thread_lock.acquire()
    isRunning = False
    thread_lock.release()

def print_log(log):
    global console_output
    console_output += log + "\n"

HISTORY_SEARCH_MAX_PAGES = 4
HISTORY_SEARCH_MAX_RESULTS = 200
NAVER_HISTORY_SEARCH_MAX_PAGES = 10
NAVER_HISTORY_STAGNANT_PAGE_LIMIT = 3
NAVER_HISTORY_GAP_QUERY_LIMIT = 200


def historical_backfill_enabled():
    try:
        with open("settings.yml", encoding="UTF8") as handle:
            config = yaml.safe_load(handle) or {}
        return bool(config.get("historical-backfill", False))
    except Exception:
        return False


def _history_episode_number(value):
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def _history_episode_label(value):
    number = _history_episode_number(value)
    if number is None:
        return str(value or "").strip()
    if number.is_integer():
        return str(int(number))
    return ("%s" % number).rstrip("0").rstrip(".")


def _history_extract_episode(text):
    text = str(text or "")
    patterns = [
        r"(?<!\d)(\d{1,3}(?:\.\d+)?)\s*(?:화|話|회)",
        r"\b(?:ep|episode)\s*[\.\-_:：#]?\s*0*(\d{1,3}(?:\.\d+)?)\b",
        r"(?:제|第)\s*(\d{1,3}(?:\.\d+)?)\s*(?:화|話|회)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return _history_episode_number(match.group(1))
    return None


def _history_normalize_title(value):
    value = unquote(str(value or "")).lower()
    value = re.sub(r"\s*(?:\d+\s*기|\d+(?:st|nd|rd|th)\s*season|season\s*\d+)\s*$", "", value, flags=re.I)
    return re.sub(r"[^0-9a-z가-힣ぁ-んァ-ヶ一-龯]+", "", value)


def _history_title_matches(result_title, anime_title):
    result = _history_normalize_title(result_title)
    wanted = _history_normalize_title(anime_title)
    if not result or not wanted:
        return False
    if wanted in result or result in wanted:
        return True

    # Search result titles often omit a trailing season marker. Requiring a
    # reasonably long shared core keeps unrelated posts on the same blog out.
    if len(wanted) >= 8:
        core = wanted[: max(8, int(len(wanted) * 0.7))]
        return core in result
    return False


def _history_candidate(url, title, anime_title, latest_episode):
    episode = _history_extract_episode(title)
    if episode is None:
        return None
    if latest_episode is not None:
        if episode >= latest_episode or episode <= 0:
            return None
    elif episode <= 0:
        return None
    if not _history_title_matches(title, anime_title):
        return None
    return {
        "url": url,
        "title": title,
        "episode": _history_episode_label(episode),
    }


def _history_add_candidate(out, seen, url, title, anime_title, latest_episode):
    if not url or url in seen or len(out) >= HISTORY_SEARCH_MAX_RESULTS:
        return
    candidate = _history_candidate(url, title, anime_title, latest_episode)
    if candidate is None:
        return
    seen.add(url)
    out.append(candidate)


def _history_search_tistory(source_url, anime_title, latest_episode):
    parsed = urlparse(source_url)
    host = parsed.netloc.lower()
    if not host:
        return []

    out = []
    seen = set()
    query = quote(anime_title, safe="")
    headers = {"User-Agent": HEADERS["User-Agent"], "Accept-Language": HEADERS["Accept-Language"]}

    for page in range(1, HISTORY_SEARCH_MAX_PAGES + 1):
        search_url = f"{parsed.scheme or 'https'}://{host}/search/{query}?page={page}"
        try:
            response = requests.get(search_url, headers=headers, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
        except Exception:
            if page == 1:
                return []
            break

        before = len(out)
        soup = BeautifulSoup(response.text, "html.parser")
        for anchor in soup.find_all("a", href=True):
            href = urljoin(search_url, anchor.get("href", ""))
            target = urlparse(href)
            if target.netloc.lower() != host:
                continue
            if re.fullmatch(r"/\d+/?", target.path or "") is None:
                continue
            title = " ".join(anchor.stripped_strings).strip()
            _history_add_candidate(out, seen, href, title, anime_title, latest_episode)

        if len(out) == before and page > 1:
            break

    return out


def _history_search_blogspot(source_url, anime_title, latest_episode):
    parsed = urlparse(source_url)
    host = parsed.netloc.lower()
    if not host:
        return []

    search_url = (
        f"{parsed.scheme or 'https'}://{host}/search?"
        + urllib.parse.urlencode({"q": anime_title, "max-results": 50})
    )
    try:
        response = requests.get(
            search_url,
            headers={"User-Agent": HEADERS["User-Agent"], "Accept-Language": HEADERS["Accept-Language"]},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
    except Exception:
        return []

    out = []
    seen = set()
    soup = BeautifulSoup(response.text, "html.parser")
    for anchor in soup.find_all("a", href=True):
        href = urljoin(search_url, anchor.get("href", ""))
        target = urlparse(href)
        if target.netloc.lower() != host:
            continue
        if re.search(r"/\d{4}/\d{2}/.+\.html$", target.path or "", re.I) is None:
            continue
        title = " ".join(anchor.stripped_strings).strip()
        _history_add_candidate(out, seen, href, title, anime_title, latest_episode)
    return out


def _history_naver_post_url(blog_id, href):
    absolute = urljoin("https://m.blog.naver.com", href or "")
    parsed = urlparse(absolute)
    match = re.search(r"/([^/?#]+)/(\d+)", parsed.path or "")
    if match:
        return f"https://blog.naver.com/{match.group(1)}/{match.group(2)}"

    params = urllib.parse.parse_qs(parsed.query)
    log_no = (params.get("logNo") or params.get("logno") or [""])[0]
    item_blog_id = (params.get("blogId") or params.get("blogid") or [blog_id])[0]
    if item_blog_id and str(log_no).isdigit():
        return f"https://blog.naver.com/{item_blog_id}/{log_no}"
    return None


def _history_naver_result_text(anchor):
    title = " ".join(anchor.stripped_strings).strip()
    container = anchor.find_parent(["li", "article"])
    if container is None:
        container = anchor.find_parent("div")
    if container is None:
        return title
    context = " ".join(container.stripped_strings).strip()
    if title and title not in context:
        context = title + " " + context
    return context or title


def _history_integer_episode(value):
    number = _history_episode_number(value)
    if number is None or number <= 0 or not number.is_integer():
        return None
    return int(number)


def _history_naver_missing_episodes(rows, latest_episode):
    latest = _history_integer_episode(latest_episode)
    if latest is None or latest <= 1:
        return []

    found = set()
    for row in rows:
        episode = _history_integer_episode(row.get("episode"))
        if episode is not None and episode < latest:
            found.add(episode)
    return [episode for episode in range(1, latest) if episode not in found]


def _history_search_naver(source_url, anime_title, latest_episode):
    blog_id, _ = _naver_post_ids(source_url)
    if not blog_id:
        return []

    out = []
    seen = set()

    def collect(search_text, max_pages, expected_episode=None, order_type="sim"):
        stagnant_pages = 0

        for page in range(1, max_pages + 1):
            search_url = (
                "https://m.blog.naver.com/PostSearchList.naver?"
                + urllib.parse.urlencode({
                    "blogId": blog_id,
                    "searchText": search_text,
                    "orderType": order_type,
                    "currentPage": page,
                    "countPerPage": 30,
                })
            )
            try:
                response = requests.get(
                    search_url,
                    headers=NAVER_REQUEST_HEADERS,
                    timeout=REQUEST_TIMEOUT,
                )
                response.raise_for_status()
            except Exception:
                if page == 1:
                    return
                break

            before = len(out)
            soup = BeautifulSoup(response.text, "html.parser")
            for anchor in soup.find_all("a", href=True):
                href = _history_naver_post_url(blog_id, anchor.get("href", ""))
                if not href or href in seen:
                    continue

                title = " ".join(anchor.stripped_strings).strip()
                context = _history_naver_result_text(anchor)
                episode = _history_extract_episode(title)
                if episode is None:
                    episode = _history_extract_episode(context)
                episode_number = _history_integer_episode(episode)
                if episode_number is None:
                    continue

                latest_number = _history_integer_episode(latest_episode)
                if latest_number is not None and episode_number >= latest_number:
                    continue
                if expected_episode is not None and episode_number != expected_episode:
                    continue

                # NAVER search results sometimes use an English release title
                # while the result snippet/body contains the Korean AniSSIA title.
                # Accept either title or surrounding search-result context.
                if not (
                    _history_title_matches(title, anime_title)
                    or _history_title_matches(context, anime_title)
                ):
                    continue

                seen.add(href)
                out.append({
                    "url": href,
                    "title": title or context,
                    "episode": _history_episode_label(episode_number),
                })
                if len(out) >= HISTORY_SEARCH_MAX_RESULTS:
                    return

            if len(out) == before:
                stagnant_pages += 1
            else:
                stagnant_pages = 0

            # A single sparse/duplicate search page is common on NAVER.
            # Only stop after several consecutive pages add nothing.
            if page > 1 and stagnant_pages >= NAVER_HISTORY_STAGNANT_PAGE_LIMIT:
                break

    # First collect broad results in both relevance and date order. The old
    # implementation used only 4 relevance pages and stopped after one page
    # without a new candidate, which produced sparse lists such as
    # 1, 13, 19, 24, 26... for a 48-episode series.
    collect(anime_title, NAVER_HISTORY_SEARCH_MAX_PAGES, order_type="sim")
    collect(anime_title, NAVER_HISTORY_SEARCH_MAX_PAGES, order_type="date")

    # Use the AniSSIA latest episode as a completeness hint. For any integer
    # episode still missing, issue a narrow one-page query for that episode.
    # This is intentionally generic for every NAVER-backed title, not a
    # title-specific workaround.
    missing = _history_naver_missing_episodes(out, latest_episode)
    if missing:
        for episode in missing[:NAVER_HISTORY_GAP_QUERY_LIMIT]:
            before = len(out)
            collect(
                f"{anime_title} {episode}화",
                1,
                expected_episode=episode,
                order_type="sim",
            )
            if len(out) == before:
                collect(
                    f"{anime_title} {episode}",
                    1,
                    expected_episode=episode,
                    order_type="sim",
                )

    remaining = _history_naver_missing_episodes(out, latest_episode)
    if remaining:
        preview = ", ".join(str(value) for value in remaining[:30])
        if len(remaining) > 30:
            preview += ", ..."
        print_log(
            f"[!] 네이버 과거 회차 누락 후보 {len(remaining)}개: {preview}화"
        )

    return out


def _history_find_posts(source_url, anime_title, latest_episode):
    lower = unquote(source_url or "").lower()
    if "tistory" in lower:
        return _history_search_tistory(source_url, anime_title, latest_episode)
    if "blogspot" in lower:
        return _history_search_blogspot(source_url, anime_title, latest_episode)
    if "naver" in lower:
        return _history_search_naver(source_url, anime_title, latest_episode)
    return []


def expand_historical_captions(json_data):
    if not historical_backfill_enabled():
        return json_data

    expanded = []
    seen = set()

    for current in json_data:
        current_url = unquote(str(current.get("website") or "")).strip()
        current_episode = _history_episode_number(current.get("episode"))
        creator = str(current.get("name") or "")
        history_rows = []

        if current_url and current_episode is not None and current_episode > 1:
            try:
                history_rows = _history_find_posts(current_url, AnimeName, current_episode)
            except Exception as exc:
                print_log(f"[-] 과거 회차 탐색 실패 ({creator}) : {exc}")

        if history_rows:
            history_rows.sort(key=lambda row: _history_episode_number(row["episode"]) or 0)
            print_log(
                f"[=] 과거 회차 탐색 ({creator}) : {len(history_rows)}개 발견 "
                f"(1화 ~ {history_rows[-1]['episode']}화 후보)"
            )

        for row in history_rows:
            key = (creator, row["episode"], row["url"])
            if key in seen:
                continue
            seen.add(key)
            expanded.append({
                "name": creator,
                "episode": row["episode"],
                "updDt": str(current.get("updDt") or ""),
                "website": row["url"],
                "_historical_backfill": True,
                "_historical_title": row["title"],
            })

        key = (
            creator,
            str(current.get("episode") or ""),
            current_url,
        )
        if key not in seen:
            seen.add(key)
            expanded.append(current)

    if len(expanded) != len(json_data):
        print_log(
            f"[=] 과거 회차 자동 탐색으로 {len(expanded) - len(json_data)}개 항목을 추가했습니다."
        )
    return expanded


# 요청함수

def requestAnimeSMI_3(anime,callback):
    requestAnimeSMI_2(anime.animeNo,anime.subject,callback);

def requestAnimeSMI_2(AnimeNo,name,callback):
    global AnimeName
    AnimeName = name
    requestAnimeSMI(AnimeNo,callback)

def requestAnimeSMI(AnimeNo,callback):
    global smiDir,isDownloadError,download_progress_count,download_progress_length,console_output,isRunning

    # 콘솔 출력 결과물 초기화
    console_output = ""

    print_log("다운경로: "+outpath)
    print_log("================================================================")

    # 로그 파일 디렉토리가 존재하지 않을시 생성
    if not os.path.exists(log_path):
        os.makedirs(log_path)

    new_filename = get_new_log_file()

    download_progress_count = 0;
    download_progress_length = 0;

    response = requests.get(
        "https://api.anissia.net/anime/caption/animeNo/" + str(AnimeNo),
        timeout=REQUEST_TIMEOUT
    )
    response.raise_for_status()

    #print_log(response.status_code)

    datas = json.loads(response.text)
    json_data = datas["data"]
    json_data = expand_historical_captions(json_data)

    #다운로드 사이즈 체크

    print_log("다운로드 사이즈를 체크 하고 있습니다.....")
    download_progress_length = get_download_progress_length(json_data);
    print_log("================================================================")

    text_to_file(console_output, log_path + new_filename)
    callback(download_progress_count,download_progress_length, "다운로드에 필요한 데이터를 확인 하고 있습니다...")

    _requestAnimeSMI(AnimeNo,callback,new_filename,json_data)

    print_log("다운로드 진행상황 => "+str(download_progress_count)+"/"+str(download_progress_length))
    print_log("작업이 종료되었습니다")

    text_to_file(console_output, log_path + new_filename)

    callback(download_progress_count,download_progress_length,"다운로드가 완료되었습니다.",True)

    unlock_Scheduler()


def requestMultipleAnimeSMI(callback):
    global smiDir,isDownloadError,download_progress_count,download_progress_length,console_output, AnimeName,AnimeNO,isRunning,quitSignal

    # 새 일괄 다운로드를 시작할 때 이전 중지 상태를 초기화합니다.
    quitSignal = False

    try:
        with open('anime.yml', encoding='UTF8') as f:
            global outpath
            config = yaml.load(f, Loader=yaml.FullLoader)

        animelist = json.loads(config['anime_list'])

        # 콘솔 출력 결과물 초기화
        console_output = ""

        print_log("다운경로: "+outpath)
        print_log("================================================================")

        # 로그 파일 디렉토리가 존재하지 않을시 생성
        if not os.path.exists(log_path):
            os.makedirs(log_path)

        new_filename = get_new_log_file()

        # 일괄 다운로드에서는 파일 수를 미리 세지 않습니다.
        # 진행률은 전체 작품 수 기준으로 표시합니다.
        download_progress_count = 0
        download_progress_length = 0
        total_anime = len(animelist)

        if total_anime == 0:
            print_log("[=] 즐겨찾기에 등록된 작품이 없습니다.")
            text_to_file(console_output, log_path + new_filename)
            callback(0, 0, "즐겨찾기에 등록된 작품이 없습니다.", True)
            return

        callback(0, total_anime, f"작품 0/{total_anime} - 다운로드 시작...")

        completed_anime = 0

        for index, k in enumerate(animelist, start=1):
            if quitSignal == True:
                print_log("[=] 사용자가 일괄 다운로드를 중지했습니다.")
                break

            AnimeName = k['Anime']
            AnimeNO = k['AnimeNo']
            base_status = f"작품 {index}/{total_anime} - {AnimeName}"

            callback(index - 1, total_anime, base_status + " 확인 중...")
            print_log(f"[{index}/{total_anime}] <{AnimeName}> 자막 정보 확인")

            try:
                response = requests.get(
                    "https://api.anissia.net/anime/caption/animeNo/" + str(AnimeNO),
                    timeout=REQUEST_TIMEOUT
                )
                response.raise_for_status()

                datas = response.json()
                json_data = datas.get("data", [])
                json_data = expand_historical_captions(json_data)

                if not json_data:
                    print_log("[=] 등록된 자막 정보가 없습니다.")
                else:
                    # 내부 파일 다운로드 콜백이 전체 진행률을 덮어쓰지 않도록
                    # 대량 모드에서는 작품 진행률로 변환해서 전달합니다.
                    def bulk_callback(_progress, _count, output="None", isFinished=False):
                        if output == "None":
                            status = "다운로드 중..."
                        else:
                            status = output
                            prefix = "<" + AnimeName + "> "
                            if status.startswith(prefix):
                                status = status[len(prefix):]
                        callback(
                            index - 1,
                            total_anime,
                            base_status + " " + status
                        )

                    _requestAnimeSMI(AnimeNO, bulk_callback, new_filename, json_data)

            except requests.Timeout:
                print_log(f"[-] 애니시아 응답 시간 초과({REQUEST_TIMEOUT}초). 다음 작품으로 넘어갑니다.")
            except requests.RequestException as e:
                print_log("[-] 애니시아 요청 실패. 다음 작품으로 넘어갑니다. : %s" % e)
            except (ValueError, KeyError, TypeError) as e:
                print_log("[-] 애니시아 응답 처리 실패. 다음 작품으로 넘어갑니다. : %s" % e)
            except Exception as e:
                print_log("[-] 작품 처리 중 오류. 다음 작품으로 넘어갑니다. : %s" % e)
                print_log(traceback.format_exc())

            completed_anime = index
            callback(index, total_anime, base_status + " 완료")
            text_to_file(console_output, log_path + new_filename)

        print_log("================================================================")

        if quitSignal == True:
            finish_message = f"다운로드가 중지되었습니다. ({completed_anime}/{total_anime})"
        else:
            finish_message = f"전체 작품 처리가 완료되었습니다. ({completed_anime}/{total_anime})"

        print_log(finish_message)
        text_to_file(console_output, log_path + new_filename)
        callback(completed_anime, total_anime, finish_message, True)

    except Exception as e:
        print_log("[-] 일괄 다운로드 중 오류가 발생했습니다. : %s" % e)
        print_log(traceback.format_exc())
        try:
            callback(0, 0, "일괄 다운로드 중 오류가 발생했습니다.", True)
        except Exception:
            pass
    finally:
        unlock_Scheduler()


def _requestAnimeSMI(AnimeNo,callback,new_filename,json_data):
    global AnimeName,smiDir,isDownloadError,download_progress_count,download_progress_length,console_output

    for k in json_data:
        
        if quitSignal == True:
            break

        isDownloadError = 0;

        name = k['name']
        episode = k['episode']
        updDt = k['updDt']
        website = unquote(k['website'])

        callback(download_progress_count,download_progress_length,"<"+AnimeName+"> 다운로드중...")
        print_log("다운로드 진행상황 => "+str(download_progress_count)+"/"+str(download_progress_length))
        print_log("ANIME SMI AUTO DOWNLOADER - Target => <"+AnimeName+">")    
        print_log("================================================================")
        print_log("> 제작자: " + name)
        print_log("> 회차: " + episode+"화")
        print_log("> 업데이트: " + updDt)
        print_log("> 주소: " + website)

        folder_name = AnimeName
        folder_name = folder_name.replace(":","")
        folder_name = folder_name.replace("/","")
        folder_name = folder_name.replace("?","")
        folder_name = folder_name.replace("<","")
        folder_name = folder_name.replace(">","")
        folder_name = folder_name.replace("*","")
        folder_name = folder_name.replace("|","")
        
        smiDir = folder_name + "/" + episode + "화/" + name + "/"

        if os.path.isfile(outpath + smiDir + "finish.txt"):
            print_log("[=] 이전에 생성된 finish.txt가 발견되어 과정이 스킵되었습니다.")
            print_log("================================================================")
            continue;

        if regrex1.match(website):
            print_log("[+] naver 검출.")
            download_naver(website,callback)
        elif regrex2.match(website):
            print_log("[+] blogspot 검출.")
            download_blogspot(website,callback)
        elif regrex3.match(website):
            print_log("[+] tistory 검출.")
            download_tistory(website,callback)
        elif website == "":
            print_log("[=] 자막 사이트가 검출되지 않았습니다.")
            isDownloadError = 1;
        else:
            print_log("[+] 일반 웹사이트 검출.")
            download_website(website,callback)
        
        if isDownloadError == 0:
            text_to_file( json.dumps(k) , outpath + smiDir + "finish.txt");
            print_log("[+] finish.txt가 생성되었습니다.")
        else:
            print_log("[-] finish.txt가 생성되지 않았습니다.")

        print_log("================================================================")
        text_to_file(console_output, log_path + new_filename)


# 내부 로직 구현

NAVER_REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
}


def _naver_post_ids(url):
    """Extract blogId/logNo from both pretty and PostView NAVER Blog URLs."""
    decoded_url = unquote(url or "")

    blog_match = re.search(r"[?&]blogId=([^&#]+)", decoded_url, re.IGNORECASE)
    log_match = re.search(r"[?&]logNo=(\d+)", decoded_url, re.IGNORECASE)
    if blog_match and log_match:
        return blog_match.group(1), log_match.group(1)

    path_match = re.search(
        r"(?:https?://)?(?:m\.)?blog\.naver\.com/([^/?#]+)/(\d+)",
        decoded_url,
        re.IGNORECASE,
    )
    if path_match:
        return path_match.group(1), path_match.group(2)

    return None, None


def _naver_file_name(file_url, fallback_name=None):
    if fallback_name:
        return unquote(str(fallback_name)).strip()

    parsed_url = urlparse(file_url)
    file_name = unquote(os.path.basename(parsed_url.path))
    if file_name:
        return file_name

    return "naver_attachment"


def _extract_naver_attachment_files(url_source):
    """Return NAVER Blog attachment entries from modern and legacy editors."""
    files = []
    seen_urls = set()

    def add_file(file_url, file_name=None, file_size=None):
        if not file_url:
            return

        file_url = str(file_url).strip().replace("&amp;", "&")
        if file_url.startswith("//"):
            file_url = "https:" + file_url

        if not file_url.startswith(("http://", "https://")):
            return

        if file_url in seen_urls:
            return

        seen_urls.add(file_url)
        files.append({
            "url": file_url,
            "name": _naver_file_name(file_url, file_name),
            "size": file_size,
        })

    soup = BeautifulSoup(url_source, "html.parser")

    # SmartEditor ONE: file components expose the real download URL through
    # data-linkdata and/or href on se-file-save-button.
    for a_tag in soup.select('a.se-file-save-button, a[data-linktype="file"]'):
        data_link = a_tag.get("data-linkdata")
        parsed_link_data = None

        if data_link:
            candidates = [
                data_link,
                data_link.replace("&quot;", '"'),
                unquote(data_link),
            ]
            for candidate in candidates:
                try:
                    parsed_link_data = json.loads(candidate)
                    break
                except (TypeError, ValueError):
                    continue

        if isinstance(parsed_link_data, dict):
            add_file(
                parsed_link_data.get("link") or parsed_link_data.get("url"),
                parsed_link_data.get("fileName")
                or parsed_link_data.get("filename")
                or parsed_link_data.get("name")
                or parsed_link_data.get("title"),
                parsed_link_data.get("fileSize") or parsed_link_data.get("size"),
            )

        href = a_tag.get("href")
        if href:
            add_file(href, a_tag.get("download") or a_tag.get_text(strip=True))

    # Some SmartEditor pages expose only the direct download anchor.
    for a_tag in soup.select('a[href*="download.blog.naver.com"]'):
        add_file(
            a_tag.get("href"),
            a_tag.get("download") or a_tag.get_text(strip=True),
        )

    # Legacy SmartEditor variant A:
    # aPostFiles[1] = JSON.parse('[...]'.replace(...))
    p_attached_file = re.compile(
        r"aPostFiles\[\d+\]\s*=\s*JSON\.parse\('(\[.*?\])'\s*\.replace",
        re.IGNORECASE | re.DOTALL,
    )
    for match in p_attached_file.finditer(url_source):
        try:
            data = match.group(1).replace("\\'", '"')
            json_data = json.loads(data)
            for each_file in json_data:
                add_file(
                    each_file.get("encodedAttachFileUrl"),
                    each_file.get("encodedAttachFileName"),
                    each_file.get("attachFileSize"),
                )
        except (TypeError, ValueError, json.JSONDecodeError) as e:
            print_log("[-] NAVER legacy attachment JSON parse failed: %s" % e)

    # Legacy SmartEditor variant B:
    # aPostFiles[1] = [{'encodedAttachFileName': '...', ...}]
    # Old NAVER posts commonly expose attachment metadata in this direct
    # JavaScript array instead of JSON.parse(...). Parse each object without
    # trying to evaluate JavaScript.
    direct_array_pattern = re.compile(
        r"aPostFiles\[\d+\]\s*=\s*(\[.*?\])\s*;",
        re.IGNORECASE | re.DOTALL,
    )
    object_pattern = re.compile(r"\{.*?\}", re.DOTALL)

    def legacy_value(obj_text, key):
        pattern = re.compile(
            r"['\"]?"
            + re.escape(key)
            + r"['\"]?\s*:\s*(['\"])(.*?)\1",
            re.IGNORECASE | re.DOTALL,
        )
        value_match = pattern.search(obj_text)
        if value_match is None:
            return None
        return (
            value_match.group(2)
            .replace(r"\/", "/")
            .replace(r"\'", "'")
            .replace(r'\\"', '"')
        )

    for array_match in direct_array_pattern.finditer(url_source):
        for obj_match in object_pattern.finditer(array_match.group(1)):
            obj_text = obj_match.group(0)
            add_file(
                legacy_value(obj_text, "encodedAttachFileUrl"),
                legacy_value(obj_text, "encodedAttachFileName"),
                legacy_value(obj_text, "attachFileSize"),
            )

    # Final safety net: some NAVER pages embed the same attachment object under
    # a different script variable. If an object still contains the canonical
    # encodedAttachFile* fields, extract it regardless of the outer variable.
    generic_object_pattern = re.compile(
        r"\{[^{}]*?encodedAttachFileUrl[^{}]*?\}",
        re.IGNORECASE | re.DOTALL,
    )
    for obj_match in generic_object_pattern.finditer(url_source):
        obj_text = obj_match.group(0)
        add_file(
            legacy_value(obj_text, "encodedAttachFileUrl"),
            legacy_value(obj_text, "encodedAttachFileName"),
            legacy_value(obj_text, "attachFileSize"),
        )

    return files


def _naver_article_links(url_source):
    """Return article links without assuming one specific NAVER editor container."""
    soup = BeautifulSoup(url_source, "html.parser")

    containers = [
        soup.select_one(".se-main-container"),
        soup.find(id="postViewArea"),
        soup.find(id="viewTypeSelector"),
        soup.select_one(".se_component_wrap"),
        soup.select_one(".post-view"),
    ]
    container = next((item for item in containers if item is not None), soup)

    links = []
    seen = set()
    for a_tag in container.find_all("a"):
        href = a_tag.get("href")
        if not href:
            continue
        href = href.strip().replace("&amp;", "&")
        if href in seen:
            continue
        seen.add(href)
        links.append(href)

    return links


def _naver_is_file_like_link(url):
    if not url:
        return False

    lower_url = unquote(url).lower()
    parsed_url = urlparse(lower_url)
    path = parsed_url.path

    if "download.blog.naver.com" in lower_url:
        return True
    if "drive.google.com/file/d/" in lower_url:
        return True
    if "drive.google.com/uc" in lower_url:
        return True
    if "docs.google.com/uc" in lower_url:
        return True
    if "drive.usercontent.google.com/download" in lower_url:
        return True

    return p_extension.match(path) is not None


def _download_naver_file(file_url, file_name, callback):
    global download_progress_count

    print_log("  Link : %s" % file_url)
    print_log("[=] 다운로드 시작 => " + file_name)

    path = outpath + smiDir
    if not os.path.exists(path):
        os.makedirs(path)

    download(file_url, path + file_name)
    print_log("[+] 파일 다운로드가 완료 되었습니다. ")
    download_progress_count += 1
    callback(download_progress_count, download_progress_length)


def download_naver(url,callback):
    global isDownloadError,download_progress_count, download_progress_length

    url_source = get_url_source_naver(url)
    if url_source is None:
        isDownloadError = 1
        return

    try:
        attachments = _extract_naver_attachment_files(url_source)

        # Prefer real NAVER attachments. This covers SmartEditor ONE as well as
        # the old aPostFiles representation.
        if attachments:
            for each_file in attachments:
                try:
                    if each_file.get("size") is not None:
                        print_log(
                            "* File : %s, Size : %s Bytes"
                            % (each_file["name"], each_file["size"])
                        )
                    else:
                        print_log("* File : %s" % each_file["name"])

                    _download_naver_file(
                        each_file["url"],
                        each_file["name"],
                        callback,
                    )
                except Exception as e:
                    print_log("[-] Error : %s" % e)
                    isDownloadError = 1
                    download_progress_count += 1
            return

        # No attachment component was found. Fall back to file-like links in
        # the article body (Google Drive, direct subtitle/archive URLs, etc.).
        file_found = 0
        for each_file in _naver_article_links(url_source):
            if not _naver_is_file_like_link(each_file):
                continue

            try:
                google_file_match = re.search(
                    r"drive\.google\.com/file/d/([^/?#]+)",
                    each_file,
                    re.IGNORECASE,
                )

                if google_file_match:
                    each_file = (
                        "https://drive.google.com/uc?id="
                        + google_file_match.group(1)
                    )

                if (
                    "drive.google.com/uc" in each_file
                    or "docs.google.com/uc" in each_file
                    or "drive.usercontent.google.com/download" in each_file
                ):
                    remotefile = urlopen(each_file, timeout=REQUEST_TIMEOUT)
                    fileName = remotefile.headers.get_filename()

                    if fileName is not None:
                        try:
                            fileName = fileName.encode("ISO-8859-1").decode("UTF-8")
                        except (UnicodeEncodeError, UnicodeDecodeError):
                            pass
                    else:
                        fileName = _naver_file_name(each_file)

                    if fileName in ("uc", "download", ""):
                        fileName = gdrive.get_file_name(each_file)

                    if not p_extension.match(fileName):
                        continue

                    print_log("  Link : %s" % each_file)
                    print_log("[=] 다운로드 시작 => " + fileName)

                    path = outpath + smiDir
                    if not os.path.exists(path):
                        os.makedirs(path)

                    gdrive.download(each_file, path + fileName, quiet=False)
                    print_log("[+] 파일 다운로드가 완료 되었습니다. ")
                    file_found = 1
                    download_progress_count += 1
                    callback(download_progress_count, download_progress_length)
                else:
                    remotefile = urlopen(each_file, timeout=REQUEST_TIMEOUT)
                    fileName = remotefile.headers.get_filename()

                    if fileName is not None:
                        try:
                            fileName = fileName.encode("ISO-8859-1").decode("UTF-8")
                        except (UnicodeEncodeError, UnicodeDecodeError):
                            pass
                    else:
                        fileName = _naver_file_name(each_file)

                    if not p_extension.match(fileName):
                        continue

                    _download_naver_file(each_file, fileName, callback)
                    file_found = 1

            except urllib.error.HTTPError as e:
                print_log("[-] 다운로드 실패 : %s" % e)
                isDownloadError = 1
                download_progress_count += 1
            except Exception as e:
                print_log("[-] Error : %s" % e)
                isDownloadError = 1
                download_progress_count += 1

        if file_found == 0:
            print_log("[-] Attached File not found !!")
            isDownloadError = 1

    except Exception as e:
        print_log("[-] Error : %s" % e)
        print_log(traceback.format_exc())
        isDownloadError = 1


def download_count_naver(url):
    url_source = get_url_source_naver(url)
    if url_source is None:
        return 0

    try:
        attachments = _extract_naver_attachment_files(url_source)
        if attachments:
            return len(attachments)

        download_count = 0
        for each_file in _naver_article_links(url_source):
            if _naver_is_file_like_link(each_file):
                download_count += 1

        return download_count
    except Exception:
        return 0


def get_url_source_naver(url):
    global isDownloadError

    try:
        blog_id, log_no = _naver_post_ids(url)

        if blog_id and log_no:
            # Modern SmartEditor content is usually easiest to parse from the
            # mobile PostView, while many legacy attachments (aPostFiles) only
            # appear in the desktop PostView. Fetch both and parse the combined
            # HTML so one parser supports both generations.
            sources = []

            mobile_url = (
                "https://m.blog.naver.com/PostView.naver?blogId="
                + quote(blog_id)
                + "&logNo="
                + log_no
                + "&proxyReferer="
            )
            print_log("   => Mobile URL : %s" % mobile_url)

            try:
                response = requests.get(
                    mobile_url,
                    headers=NAVER_REQUEST_HEADERS,
                    timeout=REQUEST_TIMEOUT,
                )
                response.raise_for_status()
                sources.append(response.text)
            except Exception as e:
                print_log("   => Mobile source failed: %s" % e)

            desktop_url = (
                "https://blog.naver.com/PostView.naver?blogId="
                + quote(blog_id)
                + "&logNo="
                + log_no
                + "&redirect=Dlog&widgetTypeCall=true"
                + "&noTrackingCode=true&directAccess=false"
            )
            print_log("   => Desktop URL : %s\n" % desktop_url)

            try:
                response = requests.get(
                    desktop_url,
                    headers=NAVER_REQUEST_HEADERS,
                    timeout=REQUEST_TIMEOUT,
                )
                response.raise_for_status()
                sources.append(response.text)
            except Exception as e:
                # Desktop PostView may reject some posts while mobile still
                # works. Keep the usable source instead of failing the post.
                print_log("   => Desktop source failed: %s" % e)

            if sources:
                return "\n<!-- NAVER SOURCE BREAK -->\n".join(sources)

            raise RuntimeError("NAVER mobile/desktop sources both failed")

        # Legacy/fallback path for unusual NAVER Blog URLs such as PostList.
        current_url = url
        for _ in range(5):
            if (
                "PostView.naver" in current_url
                or "PostList.naver" in current_url
            ):
                break

            req = request.Request(current_url, headers=NAVER_REQUEST_HEADERS)
            f = request.urlopen(req, timeout=REQUEST_TIMEOUT)
            url_info = f.info()
            charsets = client.HTTPMessage.get_charsets(url_info)
            url_charset = charsets[0] if charsets else "utf-8"
            url_source = f.read().decode(url_charset, errors="replace")

            frame_match = re.search(
                r"<iframe.*?mainFrame.*?>",
                url_source,
                re.IGNORECASE | re.DOTALL,
            )
            if frame_match is None:
                break

            src_match = re.search(
                r"src=[\'\"](.+?)[\'\"]",
                frame_match.group(0),
                re.IGNORECASE | re.DOTALL,
            )
            if src_match is None:
                break

            current_url = src_match.group(1)

        if current_url.startswith("/"):
            last_url = "https://blog.naver.com" + current_url
        elif current_url.startswith("http://") or current_url.startswith("https://"):
            last_url = current_url
        else:
            last_url = "https://blog.naver.com/" + current_url.lstrip("/")

        print_log("   => Last URL : %s\n" % last_url)

        req = request.Request(last_url, headers=NAVER_REQUEST_HEADERS)
        f = request.urlopen(req, timeout=REQUEST_TIMEOUT)
        url_info = f.info()
        charsets = client.HTTPMessage.get_charsets(url_info)
        url_charset = charsets[0] if charsets else "utf-8"
        return f.read().decode(url_charset, errors="replace")

    except Exception as e:
        print_log("[-] Error : %s" % e)
        isDownloadError = 1
        return None


def _is_download_candidate_link(file_url):
    if not file_url:
        return False

    decoded = unquote(str(file_url)).lower()
    parsed = urlparse(decoded)

    if "/attachment/" in decoded:
        return True
    if "blog.kakaocdn.net" in decoded:
        return True
    if "t1.daumcdn.net/cfile/tistory" in decoded:
        return True
    if "drive.google.com/file/d/" in decoded:
        return True
    if "drive.google.com/uc" in decoded:
        return True
    if "docs.google.com/uc" in decoded:
        return True
    if "drive.usercontent.google.com/download" in decoded:
        return True

    return p_extension.match(parsed.path) is not None


def _normalize_google_drive_link(file_url):
    if not file_url:
        return file_url

    match = re.search(
        r"drive\\.google\\.com/file/d/([^/?#]+)",
        file_url,
        re.IGNORECASE,
    )
    if match:
        return "https://drive.google.com/uc?id=" + match.group(1)

    parsed = urlparse(file_url)
    id_match = re.search(r"(?:^|&)id=([^&]+)", parsed.query)
    if id_match and (
        "drive.google.com/uc" in file_url
        or "docs.google.com/uc" in file_url
        or "drive.usercontent.google.com/download" in file_url
    ):
        return "https://drive.google.com/uc?id=" + id_match.group(1)

    return file_url


def _article_links_with_tistory_fallback(url_source, page_url):
    soup = BeautifulSoup(url_source, "html.parser")
    containers = [
        soup.select_one(".tt_article_useless_p_margin.contents_style"),
        soup.select_one(".contents_style"),
        soup.select_one(".entry-content"),
        soup.select_one(".article-view"),
        soup.select_one(".post-content"),
        soup.find("article"),
    ]
    container = next((item for item in containers if item is not None), soup)

    links = []
    seen = set()
    for a_tag in container.find_all("a"):
        href = a_tag.get("href")
        if not href:
            continue

        href = urljoin(page_url, href.strip().replace("&amp;", "&"))
        if href in seen:
            continue
        seen.add(href)

        if not _is_download_candidate_link(href):
            continue

        links.append((href, a_tag.get("download") or a_tag.get_text(strip=True)))

    return links


WINPNG_SUPPORTED_EXTENSIONS = {
    ".zip", ".ass", ".smi", ".sami", ".srt", ".7z", ".jmk"
}


def _tistory_winpng_image_urls(url_source, page_url):
    # Harne's current subtitle posts distribute files inside PNG images.
    # Other blogs are only scanned when the page explicitly references WinPNG.
    host = (urlparse(page_url).hostname or "").lower()
    if host != "harne1.tistory.com" and "winpng" not in url_source.lower():
        return []

    soup = BeautifulSoup(url_source, "html.parser")
    containers = [
        soup.select_one(".tt_article_useless_p_margin.contents_style"),
        soup.select_one(".contents_style"),
        soup.select_one(".entry-content"),
        soup.select_one(".article-view"),
        soup.select_one(".post-content"),
        soup.find("article"),
    ]
    container = next((item for item in containers if item is not None), soup)

    urls = []
    seen = set()
    for img in container.find_all("img"):
        candidates = [
            img.get("data-origin"),
            img.get("data-original"),
            img.get("data-src"),
            img.get("src"),
        ]

        srcset = img.get("srcset")
        if srcset:
            for part in srcset.split(","):
                candidates.append(part.strip().split(" ")[0])

        for candidate in candidates:
            if not candidate:
                continue

            image_url = urljoin(
                page_url,
                candidate.strip().replace("&amp;", "&"),
            )
            parsed = urlparse(image_url)
            path = parsed.path.lower()

            if not path.endswith(".png"):
                continue

            if image_url in seen:
                continue
            seen.add(image_url)
            urls.append(image_url)

    # Avoid spending a long time decoding skin icons or galleries on malformed
    # pages. Harne subtitle posts normally expose one or a few content PNGs.
    return urls[:12]


def _safe_winpng_file_name(embedded_path):
    name = os.path.basename(embedded_path.replace("\\", "/")).strip()
    name = re.sub(r'[<>:"/\\|?*]', "_", name)
    return name[:240]


def _download_tistory_winpng(url_source, page_url, callback):
    global download_progress_count

    image_urls = _tistory_winpng_image_urls(url_source, page_url)
    if not image_urls:
        return False

    request_headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/150.0.0.0 Safari/537.36"
        ),
        "Referer": page_url,
    }

    for image_url in image_urls:
        try:
            response = requests.get(
                image_url,
                headers=request_headers,
                timeout=DOWNLOAD_TIMEOUT,
            )
            response.raise_for_status()

            embedded_files, mode = extract_winpng_files(response.content)
            downloadable = []
            for embedded in embedded_files:
                file_name = _safe_winpng_file_name(embedded.path)
                extension = os.path.splitext(file_name)[1].lower()
                if not file_name or extension not in WINPNG_SUPPORTED_EXTENSIONS:
                    continue
                downloadable.append((file_name, embedded.data))

            if not downloadable:
                continue

            path = outpath + smiDir
            if not os.path.exists(path):
                os.makedirs(path)

            print_log("[+] WinPNG 검출 (%s)" % (mode or "unknown"))
            print_log("  Image : %s" % image_url)

            for file_name, file_data in downloadable:
                with open(path + file_name, "wb") as output:
                    output.write(file_data)

                print_log("[=] WinPNG 추출 => " + file_name)
                print_log("[+] 파일 다운로드가 완료 되었습니다. ")
                download_progress_count += 1
                callback(download_progress_count, download_progress_length)

            return True

        except Exception as e:
            # A normal PNG is not an error. Continue until a real WinPNG image
            # is found, and let the caller decide final failure status.
            print_log("[=] WinPNG 후보 스킵 : %s" % e)

    return False


def _requests_response_filename(response):
    disposition = response.headers.get("Content-Disposition", "")

    match = re.search(r"filename\\*=UTF-8''([^;]+)", disposition, re.IGNORECASE)
    if match:
        return unquote(match.group(1).strip().strip('"'))

    match = re.search(r'filename="?([^";]+)"?', disposition, re.IGNORECASE)
    if match:
        return match.group(1).strip()

    return None


def _download_detected_link(file_url, suggested_name, callback, session=None):
    global download_progress_count

    original_url = file_url
    file_url = _normalize_google_drive_link(file_url)
    is_google = (
        "drive.google.com/uc" in file_url
        or "docs.google.com/uc" in file_url
        or "drive.usercontent.google.com/download" in file_url
    )

    session_response = None
    if session is not None and not is_google:
        session_response = session.get(
            file_url,
            timeout=DOWNLOAD_TIMEOUT,
            stream=True,
        )
        if _is_browser_challenge_response(session_response):
            raise BrowserAuthRequired("download endpoint requires browser verification")
        session_response.raise_for_status()
        fileName = _requests_response_filename(session_response)
    else:
        remotefile = urlopen(file_url, timeout=REQUEST_TIMEOUT)
        fileName = remotefile.headers.get_filename()

    if fileName is not None:
        try:
            fileName = fileName.encode("ISO-8859-1").decode("UTF-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass
    else:
        candidate = (suggested_name or "").strip()
        if candidate and p_extension.match(candidate):
            fileName = candidate
        else:
            parsed_url = urlparse(original_url)
            fileName = unquote(os.path.basename(parsed_url.path))

    if is_google and fileName in ("uc", "download", ""):
        fileName = gdrive.get_file_name(file_url)

    if not fileName or not p_extension.match(fileName):
        if session_response is not None:
            session_response.close()
        return False

    print_log("  Link : %s" % file_url)
    print_log("[=] 다운로드 시작 => " + fileName)

    path = outpath + smiDir
    if not os.path.exists(path):
        os.makedirs(path)

    if is_google:
        gdrive.download(file_url, path + fileName, quiet=False)
    elif session_response is not None:
        with open(path + fileName, "wb") as output:
            for chunk in session_response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    output.write(chunk)
        session_response.close()
    else:
        download(file_url, path + fileName)

    print_log("[+] 파일 다운로드가 완료 되었습니다. ")
    download_progress_count += 1
    callback(download_progress_count, download_progress_length)
    return True


def download_tistory(url,callback):
    global isDownloadError,download_progress_count, download_progress_length

    url_source = get_url_source_tistory(url)
    if url_source is None:
        isDownloadError = 1
        return

    file_found = 0
    candidates = _article_links_with_tistory_fallback(url_source, url)

    try:
        old_attachment_pattern = re.compile(
            r"href=[\\'\\\"]([^\\'\\\"]*?/attachment/[^\\'\\\"]*)[\\'\\\"]",
            re.IGNORECASE | re.DOTALL,
        )
        seen = set(item[0] for item in candidates)
        for old_url in old_attachment_pattern.findall(url_source):
            old_url = urljoin(url, old_url.replace("&amp;", "&"))
            if old_url not in seen:
                candidates.insert(0, (old_url, ""))
                seen.add(old_url)

        for each_file, suggested_name in candidates:
            try:
                if _download_detected_link(each_file, suggested_name, callback):
                    file_found = 1
            except urllib.error.HTTPError as e:
                print_log("[-] 다운로드 실패 : %s" % e)
                isDownloadError = 1
                download_progress_count += 1
            except Exception as e:
                print_log("[-] Error : %s" % e)
                print_log(traceback.format_exc())
                isDownloadError = 1
                download_progress_count += 1

        # Harne and newer WinPNG-based Tistory posts may intentionally expose
        # no ordinary attachment link. Decode the content PNG itself.
        if file_found == 0:
            if _download_tistory_winpng(url_source, url, callback):
                file_found = 1

        if file_found == 0:
            print_log("[-] Attached File not found !!")
            isDownloadError = 1

    except Exception as e:
        print_log("[-] Error : %s" % e)
        print_log(traceback.format_exc())
        isDownloadError = 1


def download_count_tistory(url):
    url_source = get_url_source_tistory(url)
    if url_source is None:
        return 0

    try:
        candidates = _article_links_with_tistory_fallback(url_source, url)
        old_attachment_pattern = re.compile(
            r"href=[\\'\\\"]([^\\'\\\"]*?/attachment/[^\\'\\\"]*)[\\'\\\"]",
            re.IGNORECASE | re.DOTALL,
        )

        seen = set(item[0] for item in candidates)
        for old_url in old_attachment_pattern.findall(url_source):
            old_url = urljoin(url, old_url.replace("&amp;", "&"))
            seen.add(old_url)

        if seen:
            return len(seen)

        if _tistory_winpng_image_urls(url_source, url):
            return 1

        return 0
    except Exception:
        return 0


def get_url_source_tistory(url):
    global isDownloadError
    try:
        try:
            f = request.urlopen(url, timeout=REQUEST_TIMEOUT)
        except Exception as e:
            # 한글 URL 검출시 quote로 감싸야됨
            # 'ascii' codec can't encode characters in position 11-13: ordinal not in range(128) 방지
            last_slash_index = url.rfind('/')
            body = url[:last_slash_index]
            query = quote(url[last_slash_index:])
            #print_log("출력=> "+body + query)
            f = request.urlopen(body + query, timeout=REQUEST_TIMEOUT)

        url_info = f.info()
        url_charset = client.HTTPMessage.get_charsets(url_info)[0]
        url_source = f.read().decode(url_charset)
        return url_source
    except Exception as e:
        print_log("[-] Error : %s" % e)
        print_log(traceback.format_exc())
        isDownloadError = 1;
        return None;

def _blogspot_download_candidates(url_source, page_url):
    soup = BeautifulSoup(url_source, "html.parser")
    containers = [
        soup.select_one(".post-body"),
        soup.select_one(".post-content"),
        soup.find("article"),
    ]
    container = next((item for item in containers if item is not None), soup)

    candidates = []
    seen = set()
    for a_tag in container.find_all("a"):
        href = a_tag.get("href")
        if not href:
            continue

        href = urljoin(page_url, href.strip().replace("&amp;", "&"))
        if href in seen:
            continue
        seen.add(href)

        if not _is_download_candidate_link(href):
            continue

        candidates.append((href, a_tag.get("download") or a_tag.get_text(strip=True)))

    return candidates


def download_blogspot(url,callback):
    global isDownloadError, download_progress_count, download_progress_length

    url_source = get_url_source_blogspot(url)
    if url_source is None:
        isDownloadError = 1
        return

    candidates = _blogspot_download_candidates(url_source, url)
    if not candidates:
        print_log("[-] Attached File not found !!")
        isDownloadError = 1
        return

    isDownloaded = 0

    for each_file, suggested_name in candidates:
        try:
            if _download_detected_link(each_file, suggested_name, callback):
                isDownloaded = 1
        except urllib.error.HTTPError as e:
            print_log("[-] 다운로드 실패 : %s" % e)
            isDownloadError = 1
            download_progress_count += 1
        except Exception as e:
            print_log("[-] Error : %s" % e)
            print_log(traceback.format_exc())
            isDownloadError = 1
            download_progress_count += 1

    if isDownloaded == 0:
        isDownloadError = 1


def download_count_blogspot(url):
    url_source = get_url_source_blogspot(url)
    if url_source is None:
        return 0

    try:
        return len(_blogspot_download_candidates(url_source, url))
    except Exception:
        return 0


def get_url_source_blogspot(url):
    global isDownloadError
    try:
        try:
            f = request.urlopen(url, timeout=REQUEST_TIMEOUT)
        except Exception as e:
            # 한글 URL 검출시 quote로 감싸야됨
            # 'ascii' codec can't encode characters in position 11-13: ordinal not in range(128) 방지
            last_slash_index = url.rfind('/')
            body = url[:last_slash_index]
            query = quote(url[last_slash_index:])
            #print_log("출력=> "+body + query)
            f = request.urlopen(body + query, timeout=REQUEST_TIMEOUT)
        url_info = f.info()
        url_charset = client.HTTPMessage.get_charsets(url_info)[0]
        url_source = f.read().decode(url_charset)
        return url_source
    except Exception as e:
        print_log("[-] Error : %s" % e)
        isDownloadError = 1;
        return None;

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
}

class BrowserAuthRequired(RuntimeError):
    pass


def _is_erulabo_url(url):
    try:
        host = (urlparse(url).hostname or "").lower()
        return host == "erulabo.com" or host.endswith(".erulabo.com")
    except Exception:
        return False


def _is_browser_challenge_response(response):
    if response is None:
        return True

    if response.status_code in (403, 429, 503):
        return True

    content_type = (response.headers.get("Content-Type") or "").lower()
    if "html" not in content_type and "json" not in content_type and "text/" not in content_type:
        return False

    try:
        body = (response.text or "")[:500000].lower()
    except Exception:
        body = ""

    markers = (
        "cf-turnstile",
        "challenges.cloudflare.com",
        "cf-chl-",
        "just a moment",
        "verify you are human",
    )
    return any(marker in body for marker in markers)


def _session_from_browser_cookies(cookies, user_agent=None):
    session = requests.Session()
    session.headers.update(HEADERS)
    if user_agent:
        session.headers["User-Agent"] = user_agent

    for cookie in cookies or []:
        name = cookie.get("name")
        value = cookie.get("value")
        if not name:
            continue

        kwargs = {}
        domain = cookie.get("domain")
        path = cookie.get("path")
        if domain:
            kwargs["domain"] = domain
        if path:
            kwargs["path"] = path

        session.cookies.set(name, value or "", **kwargs)

    return session


def _request_browser_authenticated_session(url):
    if browser_auth_provider is None:
        print_log("[-] 사용자 인증이 필요하지만 내장 브라우저를 사용할 수 없습니다.")
        return None

    print_log("[!] CAPTCHA / Cloudflare 사용자 인증이 필요합니다.")
    auth_result = browser_auth_provider(url)

    if not auth_result:
        print_log("[=] 사용자 인증이 취소되었습니다.")
        return None

    if isinstance(auth_result, dict):
        cookies = auth_result.get("cookies")
        user_agent = auth_result.get("user_agent")
    else:
        cookies = auth_result
        user_agent = None

    if not cookies:
        print_log("[=] 브라우저 인증 쿠키를 확인하지 못했습니다.")
        return None

    print_log("[+] 브라우저 인증 정보를 가져왔습니다. 다운로드를 다시 시도합니다.")
    return _session_from_browser_cookies(cookies, user_agent=user_agent)


def _erulabo_page(session, url):
    response = session.get(url, timeout=15)

    if _is_browser_challenge_response(response):
        raise BrowserAuthRequired("Erulabo browser verification required")

    response.raise_for_status()
    return response


def _erulabo_download_url(session, page_url, file_url):
    page_response = _erulabo_page(session, page_url)
    csrf_token = extract_csrf_token(page_response.text)

    if not csrf_token:
        raise RuntimeError("Erulabo CSRF token not found")

    token_response = session.post(
        file_url + "/token",
        json={},
        headers={
            "Accept": "*/*",
            "Content-Type": "application/json",
            "X-CSRF-TOKEN": csrf_token,
            "X-Requested-With": "XMLHttpRequest",
            "Referer": page_url,
            "Origin": "https://erulabo.com",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
        },
        timeout=15,
    )

    if _is_browser_challenge_response(token_response):
        raise BrowserAuthRequired("Erulabo token endpoint requires browser verification")

    token_response.raise_for_status()
    data = token_response.json()
    return data.get("download_url", "")


def extract_csrf_token(html, url_source=None):
    match = re.search(r'<meta\s+name="csrf-token"\s+content="([^"]+)"', html)
    return match.group(1) if match else None

def download_website(url,callback):
    global isDownloadError, download_progress_count, download_progress_length

    if _is_erulabo_url(url):
        download_erulabo(url, callback)
        return

    url_source = get_url_source_website(url)
    if url_source is None:
        isDownloadError = 1
        return

    soup = BeautifulSoup(url_source, "html.parser")
    isDownloaded = find_blog_standard(soup, callback)

    if isDownloaded == 0:
        isDownloadError = 1


def find_blog_standard(temps,callback):
    global isDownloadError, download_progress_count, download_progress_length

    if temps is None:
        return 0

    for a in temps.find_all("a"):
        each_file = a.get("href")
        if not each_file:
            continue

        each_file = each_file.replace("&amp;", "&")
        if not _is_download_candidate_link(each_file):
            continue

        try:
            if _download_detected_link(
                each_file,
                a.get("download") or a.get_text(strip=True),
                callback,
            ):
                return 1
        except urllib.error.HTTPError as e:
            print_log("[-] 다운로드 실패 : %s" % e)
            isDownloadError = 1
            download_progress_count += 1
        except Exception as e:
            print_log("[-] Error : %s" % e)
            print_log(traceback.format_exc())
            isDownloadError = 1
            download_progress_count += 1

    return 0


def download_erulabo(url, callback):
    global isDownloadError

    session = requests.Session()
    session.headers.update(HEADERS)

    try:
        try:
            page_response = _erulabo_page(session, url)
        except BrowserAuthRequired:
            session = _request_browser_authenticated_session(url)
            if session is None:
                isDownloadError = 1
                return
            page_response = _erulabo_page(session, url)

        soup = BeautifulSoup(page_response.text, "html.parser")
        if find_blog_1(soup, url, callback, session=session) == 0:
            isDownloadError = 1

    except Exception as e:
        print_log("[-] Erulabo 다운로드 실패 : %s" % e)
        print_log(traceback.format_exc())
        isDownloadError = 1


def find_blog_1(temps, url, callback, session=None):
    """Download Erulabo attachments, asking the GUI for human auth when needed."""
    global isDownloadError, download_progress_count, download_progress_length

    if session is None:
        session = requests.Session()
        session.headers.update(HEADERS)

    links = temps.find_all("button", attrs={"data-file-url": True})
    if not links:
        print_log("[-] Erulabo 첨부 파일을 찾지 못했습니다.")
        return 0

    for button in links:
        each_file = urljoin("https://erulabo.com", button.attrs["data-file-url"])
        each_file = each_file.replace("&amp;", "&")

        try:
            try:
                download_url = _erulabo_download_url(session, url, each_file)
            except BrowserAuthRequired:
                session = _request_browser_authenticated_session(url)
                if session is None:
                    isDownloadError = 1
                    return 0
                download_url = _erulabo_download_url(session, url, each_file)

            if not download_url:
                print_log("[-] Erulabo 다운로드 URL을 받지 못했습니다.")
                continue

            resolved_url = download_url
            redirect_response = session.get(
                download_url,
                allow_redirects=False,
                timeout=15,
            )

            if _is_browser_challenge_response(redirect_response):
                raise BrowserAuthRequired("Erulabo download endpoint requires browser verification")

            if redirect_response.status_code in (301, 302, 303, 307, 308):
                location = redirect_response.headers.get("Location", "")
                if location:
                    resolved_url = urljoin(download_url, location)
                    print_log("  Redirect : " + resolved_url)

            suggested_name = button.get("download") or button.get_text(strip=True)
            if _download_detected_link(
                resolved_url,
                suggested_name,
                callback,
                session=session,
            ):
                return 1

        except BrowserAuthRequired:
            print_log("[-] 다운로드 단계에서 사용자 인증이 다시 필요합니다.")
            isDownloadError = 1
            return 0
        except urllib.error.HTTPError as e:
            print_log("[=] 해당 URL은 스킵되었습니다. : %s" % e)
            download_progress_count += 1
            return 0
        except Exception as e:
            print_log("[-] Error : %s" % e)
            print_log(traceback.format_exc())
            download_progress_count += 1
            return 0

    return 0


def download_count_website(url):

    # Erulabo는 사전 카운트 단계에서 CAPTCHA를 띄우지 않습니다.
    if _is_erulabo_url(url):
        return 1

    url_source = get_url_source_website(url)

    if url_source is None:
        return 0

    soup = BeautifulSoup(url_source, 'html.parser')
    temps = soup.find('div')

    links = temps.find_all("a")

    download_count = 0;

    for a in links:
        each_file = a.attrs['href']

        try:
            each_file = each_file.replace('&amp;','&');
            # 구글 드라이브 주소가 검출되었을때
            if bool(p_google.match(each_file)):
                print_log("[+] 구글 드라이브 주소가 검출되었습니다.")
                download_count += 1
        except Exception as e:
            download_count = 0

    return download_count    

def get_url_source_website(url):
    global isDownloadError
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    try:
        try:
            req = request.Request(url, headers=headers)
            f = request.urlopen(req, timeout=REQUEST_TIMEOUT)
        except Exception as e:
            # 한글 URL 검출시 quote로 감싸야됨
            # 'ascii' codec can't encode characters in position 11-13: ordinal not in range(128) 방지
            last_slash_index = url.rfind('/')
            body = url[:last_slash_index]
            query = quote(url[last_slash_index:])
            #print_log("출력=> "+body + query)
            f = request.urlopen(body + query, timeout=REQUEST_TIMEOUT)
        url_info = f.info()
        url_charset = client.HTTPMessage.get_charsets(url_info)[0]
        url_source = f.read().decode(url_charset)
        return url_source
    except Exception as e:
        print_log("[-] Error : %s" % e)
        isDownloadError = 1;
        return None;

def run_scheduler(callback):
    with open('anime.yml', encoding='UTF8') as f:
        global outpath
        config = yaml.load(f, Loader=yaml.FullLoader)

        if config['download_path'] != "":
            outpath = config['download_path'] + "/"

        print_log("다운경로: "+outpath)

        animelist = json.loads(config['anime_list'])

        print_log("================================================================")

        for k in animelist:
            global AnimeName,AnimeNO
            AnimeName = k['Anime']
            AnimeNO = k['AnimeNo']
            requestAnimeSMI(AnimeNO,callback);

if __name__ == "__main__":
    print_log("hello")
    #run_scheduler()

