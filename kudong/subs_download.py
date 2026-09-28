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
from http import client
from urllib import request
from urllib.request import urlopen
from urllib.parse import unquote
from urllib.parse import quote
from urllib.parse import urlparse
from datetime import datetime
from bs4 import BeautifulSoup

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

    # Legacy SmartEditor: aPostFiles[1] = JSON.parse('[...]'.replace(...))
    p_attached_file = re.compile(
        r"aPostFiles\[1\]\s*=\s*JSON\.parse\('(\[.*?\])'\s*\.replace",
        re.IGNORECASE | re.DOTALL,
    )
    match = p_attached_file.search(url_source)
    if match:
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
                print_log("[=] 해당 URL은 스킵되었습니다. : %s" % e)
                download_progress_count += 1
            except Exception as e:
                print_log("[-] Error : %s" % e)
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

        # Modern NAVER Blog pages are more stable through the mobile PostView
        # endpoint and do not require the legacy mainFrame traversal.
        if blog_id and log_no:
            last_url = (
                "https://m.blog.naver.com/PostView.naver?blogId="
                + quote(blog_id)
                + "&logNo="
                + log_no
                + "&proxyReferer="
            )
            print_log("   => Last URL : %s\n" % last_url)

            response = requests.get(
                last_url,
                headers=NAVER_REQUEST_HEADERS,
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            return response.text

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


def download_tistory(url,callback):
    global isDownloadError,download_progress_count, download_progress_length
    url_source = get_url_source_tistory(url)

    if url_source is None:
        return

    # find 's1.daumcdn.net/cfs.tistory'
    if url_source.find("t1.daumcdn.net/tistory") == -1:
        print_log("[-] It is not a Tistory Blog")
        isDownloadError = 1;
        return;

    try:
        # find all 'attach file link'
        p_attach = re.compile(r"href=[\'\"](\S+?/attachment/.*?)[\'\"]\s*.*?/> (.*?)</", re.IGNORECASE | re.DOTALL)
        result = p_attach.findall(url_source)

        if result:
            
            for each_file in result:
                file_url = each_file[0]
                if each_file[1] == "":
                    file_name = file_url[file_url.rfind('/') + 1:]
                else:
                    file_name = each_file[1]
                print_log("* File : %s" % file_name)
                print_log("  Link : %s" % file_url)
                print_log("[=] 다운로드 시작 => "+file_name)

                path = outpath + smiDir
                if not os.path.exists(path):
                    os.makedirs(path)

                download(file_url, path + file_name)
                print_log("[+] 파일 다운로드가 완료 되었습니다. ")
                download_progress_count += 1
                callback(download_progress_count,download_progress_length)
        else:
            soup = BeautifulSoup(url_source, 'html.parser')
            temps = soup.find('div',class_="tt_article_useless_p_margin contents_style")    
        
            if(temps is None):
                temps = soup.find('div', {'class': 'contents_style'})

            links = temps.find_all("a")
            file_found = 0;

            p_attach = re.compile(r"(.*(googleusercontent).*)")
            p_google = re.compile(r"(.*(https://drive.google.com/file/d/).*)")

            for a in links:
                if a.get('href') == None:
                    continue;
                each_file = a.attrs['href']
                # print_log("href = "+each_file)
                try:
                    each_file = each_file.replace('&amp;','&');

                    # 구글 드라이브 주소가 검출되었을때
                    if bool(p_google.match(each_file)):

                        start_index = each_file.find("/d/") + 3;
                        end_index =  each_file.rfind("/view");

                        key = each_file[start_index:end_index]
                        each_file = "https://drive.google.com/uc?id="+key

                        remotefile = urlopen(each_file, timeout=REQUEST_TIMEOUT)
                        fileName = remotefile.headers.get_filename();

                        if fileName is not None:
                            fileName = fileName.encode('ISO-8859-1').decode('UTF-8');
                        else:
                            parsed_url = urlparse(each_file)
                            fileName = os.path.basename(parsed_url.path)
                            fileName = unquote(fileName)

                        path = outpath + smiDir

                        if fileName == "uc":
                            fileName = gdrive.get_file_name(each_file)
                    
                        if(not p_extension.match(fileName)):
                            download_progress_count += 1
                            callback(download_progress_count,download_progress_length)
                            continue;

                        print_log("[=] 다운로드 시작 => "+ fileName)

                        if not os.path.exists(path):
                            os.makedirs(path)

                        gdrive.download(each_file, path + fileName, quiet=False)
                        print_log("[+] 파일 다운로드가 완료 되었습니다. ")

                        file_found = 1;
                        download_progress_count += 1
                        callback(download_progress_count,download_progress_length)

                    # 일반 다운로드 주소가 검출되었을때
                    elif bool(p_attach.match(each_file)) == False:
                        print_log("  Link : %s" % each_file)
                        remotefile = urlopen(each_file, timeout=REQUEST_TIMEOUT)
                        fileName = remotefile.headers.get_filename();

                        if fileName is not None:
                            fileName = fileName.encode('ISO-8859-1').decode('UTF-8');
                        else:
                            parsed_url = urlparse(each_file)
                            fileName = os.path.basename(parsed_url.path)
                            fileName = unquote(fileName)

                        print_log("[=] 다운로드 시작 => "+fileName)

                        path = outpath + smiDir
                        if not os.path.exists(path):
                            os.makedirs(path)

                        download(each_file, path + fileName);
                        isDownloaded = 1;
                        file_found = 1;
                        print_log("[+] 파일 다운로드가 완료 되었습니다. ")
                        download_progress_count += 1
                        callback(download_progress_count,download_progress_length)

                except urllib.error.HTTPError as e:
                    print_log("[=] 해당 URL은 스킵되었습니다. : %s" % e)
                    download_progress_count += 1    
                except Exception as e:
                    print_log("[-] Error : %s" % e)
                    print_log(traceback.format_exc())
                    download_progress_count += 1
            
            if(file_found == 0):
                print_log("[-] Attached File not found !!")
                isDownloadError = 1;
    
    except Exception as e:
        print_log("[-] Error : %s" % e)
        print_log(traceback.format_exc())
        isDownloadError = 1;   

def download_count_tistory(url):
    url_source = get_url_source_tistory(url)

    if url_source is None:
        return 0
    
    if url_source.find("t1.daumcdn.net/tistory") == -1:
        return 0;

    download_count = 0

    try:
        p_attach = re.compile(r"href=[\'\"](\S+?/attachment/.*?)[\'\"]\s*.*?/> (.*?)</", re.IGNORECASE | re.DOTALL)
        result = p_attach.findall(url_source)

        if result:
            return result.len()
        else:
            soup = BeautifulSoup(url_source, 'html.parser')
            temps = soup.find('div',class_="tt_article_useless_p_margin contents_style")    
            
            if(temps is None):
                temps = soup.find('div', {'class': 'contents_style'})

            links = temps.find_all("a")

            p_attach = re.compile(r"(.*(googleusercontent).*)")
            p_google = re.compile(r"(.*(https://drive.google.com/file/d/).*)")

            for a in links:
                if a.get('href') == None:
                    continue;
                each_file = a.attrs['href']
                try:
                    each_file = each_file.replace('&amp;','&');
                    # 구글 드라이브 주소가 검출되었을때
                    if bool(p_google.match(each_file)):
                        download_count += 1

                    # 일반 다운로드 주소가 검출되었을때
                    elif bool(p_attach.match(each_file)) == False:
                        download_count += 1

                except Exception as e:
                    download_count += 0

    except Exception as e:
        download_count += 0   
    
    return download_count

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

def download_blogspot(url,callback):
    global isDownloadError, download_progress_count, download_progress_length
    url_source = get_url_source_blogspot(url)

    if url_source is None:
        return

    # p_attach = re.compile(r"<div class=\'post-body.*?\'[^>]*>((?:(?:(?!<div[^>]*>|</div>).)+|<div[^>]*>([\s\S]*?)</div>)*)</div>", re.IGNORECASE | re.DOTALL)   
    # result = p_attach.findall(url_source)

    soup = BeautifulSoup(url_source, 'html.parser')
    temps = soup.find('div',class_="post-body")

    links = temps.find_all("a")

    p_attach = re.compile(r"(.*(googleusercontent).*)")
    p_google = re.compile(r"(.*(https://drive.google.com/file/d/).*)")
    p_google_2 = re.compile(r"(.*(https://docs.google.com/uc).*)")
    p_google_3 = re.compile(r"(.*(https://drive.usercontent.google.com/download).*)")

    isDownloaded = 0;

    for a in links:
        each_file = a.attrs['href']
        #print_log("href = "+each_file)
        try:
            each_file = each_file.replace('&amp;','&');

            if bool(p_google_2.match(each_file)):
                start_index = each_file.find("&id=") + 4;
                end_index =  each_file.rfind("&confirm");
                each_file = "https://drive.google.com/file/d/" + each_file[start_index:end_index] + "/view"
            
            if bool(p_google_3.match(each_file)):
                start_index = each_file.find("?id=") + 4;
                end_index =  each_file.rfind("&export");
                each_file = "https://drive.google.com/file/d/" + each_file[start_index:end_index] + "/view"

            # 구글 드라이브 주소가 검출되었을때
            if bool(p_google.match(each_file)):

                start_index = each_file.find("/d/") + 3;
                end_index =  each_file.rfind("/view");

                key = each_file[start_index:end_index]
                each_file = "https://drive.google.com/uc?id="+key

                remotefile = urlopen(each_file, timeout=REQUEST_TIMEOUT)
                fileName = remotefile.headers.get_filename();

                if fileName is not None:
                    fileName = fileName.encode('ISO-8859-1').decode('UTF-8');
                else:
                    parsed_url = urlparse(each_file)
                    fileName = os.path.basename(parsed_url.path)
                    fileName = unquote(fileName)

                path = outpath + smiDir

                if fileName == "uc":
                    fileName = gdrive.get_file_name(each_file)

                #print_log(fileName);

                if(not p_extension.match(fileName)):
                    download_progress_count += 1
                    callback(download_progress_count,download_progress_length)
                    continue;

                print_log("[=] 다운로드 시작 => "+ fileName)

                if not os.path.exists(path):
                    os.makedirs(path)

                gdrive.download(each_file, path + fileName, quiet=False)
                print_log("[+] 파일 다운로드가 완료 되었습니다. ")
                    
                isDownloaded = 1;
                download_progress_count += 1
                callback(download_progress_count,download_progress_length)
            # 일반 다운로드 주소가 검출되었을때
            elif bool(p_attach.match(each_file)) == False:
                print_log("  Link : %s" % each_file)
                remotefile = urlopen(each_file, timeout=REQUEST_TIMEOUT)
                fileName = remotefile.headers.get_filename();

                if fileName is not None:
                    try:
                        fileName = fileName.encode('ISO-8859-1').decode('UTF-8');
                    except Exception as e:
                        fileName = fileName.encode('UTF-8').decode('ISO-8859-1');
                        fileName = fileName.encode('ISO-8859-1').decode('UTF-8');
                else:
                    parsed_url = urlparse(each_file)
                    fileName = os.path.basename(parsed_url.path)
                    fileName = unquote(fileName)

                if(not p_extension.match(fileName)):
                   download_progress_count += 1
                   callback(download_progress_count,download_progress_length)
                   continue;
                
                print_log("[=] 다운로드 시작 => "+fileName)

                path = outpath + smiDir
                if not os.path.exists(path):
                    os.makedirs(path)

                download(each_file, path + fileName);
                isDownloaded = 1;
                print_log("[+] 파일 다운로드가 완료 되었습니다. ")
                download_progress_count += 1
                callback(download_progress_count,download_progress_length)

        except urllib.error.HTTPError as e:
            print_log("[=] 해당 URL은 스킵되었습니다. : %s" % e)
            download_progress_count += 1 
        except Exception as e:
            print_log("[-] Error : %s" % e)
            print_log(traceback.format_exc())
            download_progress_count += 1

    if isDownloaded == 0:
        isDownloadError = 1;

def download_count_blogspot(url):

    url_source = get_url_source_blogspot(url)

    if url_source is None:
        return 0

    soup = BeautifulSoup(url_source, 'html.parser')
    temps = soup.find('div',class_="post-body")

    links = temps.find_all("a")

    p_attach = re.compile(r"(.*(googleusercontent).*)")
    p_google = re.compile(r"(.*(https://drive.google.com/file/d/).*)")

    download_count = 0;

    for a in links:
        each_file = a.attrs['href']

        try:
            each_file = each_file.replace('&amp;','&');
            # 구글 드라이브 주소가 검출되었을때
            if bool(p_google.match(each_file)):
                print_log("[+] 구글 드라이브 주소가 검출되었습니다.")
                download_count += 1
            # 일반 다운로드 주소가 검출되었을때
            elif bool(p_attach.match(each_file)) == False:
                print_log("[+] 일반 다운로드 주소가 검출되었습니다.")
                download_count += 1
        except Exception as e:
            download_count += 0
    return download_count    

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

def extract_csrf_token(html, url_source=None):
    match = re.search(r'<meta\s+name="csrf-token"\s+content="([^"]+)"', html)
    return match.group(1) if match else None

def download_website(url,callback):
    global isDownloadError, download_progress_count, download_progress_length
    url_source = get_url_source_website(url)

    if url_source is None:
        return

    soup = BeautifulSoup(url_source, 'html.parser')
    temps = soup.find('div')

    isDownloaded = 0;
    isDownloaded = find_blog_standard(temps,callback)

    if isDownloaded == 0:
        isDownloadError = 1;

def find_blog_standard(temps,callback):
    global isDownloadError, download_progress_count, download_progress_length

    links = temps.find_all("a")

    for a in links:
        each_file = a.attrs['href']
        #print_log("href = "+each_file)

        try:
            each_file = each_file.replace('&amp;','&');

            if bool(p_google_2_1.match(each_file)):
                start_index = each_file.find("&id=") + 4;
                end_index =  each_file.rfind("&confirm");
                each_file = "https://drive.google.com/file/d/" + each_file[start_index:end_index] + "/view"

            if bool(p_google_2_2.match(each_file)):
                start_index = each_file.find("&id=") + 4;
                end_index =  len(each_file);
                each_file = "https://drive.google.com/file/d/" + each_file[start_index:end_index] + "/view"

            if bool(p_google_3.match(each_file)):
                start_index = each_file.find("?id=") + 4;
                end_index =  each_file.rfind("&export");
                each_file = "https://drive.google.com/file/d/" + each_file[start_index:end_index] + "/view"

            # 구글 드라이브 주소가 검출되었을때
            if bool(p_google.match(each_file)):

                start_index = each_file.find("/d/") + 3;
                end_index =  each_file.rfind("/view");

                key = each_file[start_index:end_index]
                each_file = "https://drive.google.com/uc?id="+key

                remotefile = urlopen(each_file, timeout=REQUEST_TIMEOUT)
                fileName = remotefile.headers.get_filename();

                if fileName is not None:
                    fileName = fileName.encode('ISO-8859-1').decode('UTF-8');
                else:
                    parsed_url = urlparse(each_file)
                    fileName = os.path.basename(parsed_url.path)
                    fileName = unquote(fileName)

                path = outpath + smiDir

                if fileName == "uc":
                    fileName = gdrive.get_file_name(each_file)

                #print_log(fileName);

                if(not p_extension.match(fileName)):
                    download_progress_count += 1
                    callback(download_progress_count,download_progress_length)
                    continue;

                print_log("[=] 다운로드 시작 => "+ fileName)

                if not os.path.exists(path):
                    os.makedirs(path)

                gdrive.download(each_file, path + fileName, quiet=False)
                print_log("[+] 파일 다운로드가 완료 되었습니다. ")
                    
                download_progress_count += 1
                callback(download_progress_count,download_progress_length)
                return 1;
        except urllib.error.HTTPError as e:
            print_log("[=] 해당 URL은 스킵되었습니다. : %s" % e)
            download_progress_count += 1
            return 0;
        except Exception as e:
            print_log("[-] Error : %s" % e)
            print_log(traceback.format_exc())
            download_progress_count += 1
            return 0;
    return 0;

# Cloudflare Turnstile 인증으로 Deprecated 
def find_blog_1(temps,url,callback):
    global isDownloadError, download_progress_count, download_progress_length

    blog_1_url = re.compile(r"(.*(https://erulabo.com/file).*)")
    links = temps.find_all("button", attrs={"data-file-url": True})

    for a in links:
        each_file = "https://erulabo.com" + a.attrs['data-file-url']
        #print("data-file-url = "+each_file)

        try:
            each_file = each_file.replace('&amp;','&');

            if bool(blog_1_url.match(each_file)):

                # Step 1: 게시글 접근 → 쿠키 + CSRF 토큰
                session = requests.Session()
                session.headers.update(HEADERS)

                resp = session.get(url, timeout=15)
                resp.raise_for_status()
                csrf_token = extract_csrf_token(resp.text)

                token_url = each_file + "/token";
                token_resp = session.post(
                    token_url,
                    json={},  # Content-Length: 2 (빈 JSON body)
                    headers={
                        "Accept": "*/*",
                        "Content-Type": "application/json",
                        "X-CSRF-TOKEN": csrf_token,
                        "X-Requested-With": "XMLHttpRequest",
                        "Referer": url,
                        "Origin": "https://erulabo.com",
                        "Sec-Fetch-Dest": "empty",
                        "Sec-Fetch-Mode": "cors",
                        "Sec-Fetch-Site": "same-origin",
                    },
                    timeout=15,
                );

                # Step 2: POST /file/{uuid}/token 으로 다운로드 URL 획득
                data = token_resp.json();
                download_url = data.get("download_url", ""); 

                if download_url:
                    dl_resp = session.get(download_url, allow_redirects=False, timeout=15)

                    if dl_resp.status_code in (301, 302, 303, 307, 308): # Google Drive URL
                        each_file = dl_resp.headers.get("Location", "")
                        print_log("Google Drive URL: " + each_file)
                    else: # 리다이렉트 없음
                        each_file = download_url

            if bool(p_google_2_1.match(each_file)):
                start_index = each_file.find("&id=") + 4;
                end_index =  each_file.rfind("&confirm");
                each_file = "https://drive.google.com/file/d/" + each_file[start_index:end_index] + "/view"

            if bool(p_google_2_2.match(each_file)):
                start_index = each_file.find("&id=") + 4;
                end_index =  len(each_file);
                each_file = "https://drive.google.com/file/d/" + each_file[start_index:end_index] + "/view"

            if bool(p_google_3.match(each_file)):
                start_index = each_file.find("?id=") + 4;
                end_index =  each_file.rfind("&export");
                each_file = "https://drive.google.com/file/d/" + each_file[start_index:end_index] + "/view"

            # 구글 드라이브 주소가 검출되었을때
            if bool(p_google.match(each_file)):

                start_index = each_file.find("/d/") + 3;
                end_index =  each_file.rfind("/view");

                key = each_file[start_index:end_index]
                each_file = "https://drive.google.com/uc?id="+key

                remotefile = urlopen(each_file, timeout=REQUEST_TIMEOUT)
                fileName = remotefile.headers.get_filename();

                if fileName is not None:
                    fileName = fileName.encode('ISO-8859-1').decode('UTF-8');
                else:
                    parsed_url = urlparse(each_file)
                    fileName = os.path.basename(parsed_url.path)
                    fileName = unquote(fileName)

                path = outpath + smiDir

                if fileName == "uc":
                    fileName = gdrive.get_file_name(each_file)

                #print_log(fileName);

                if(not p_extension.match(fileName)):
                    download_progress_count += 1
                    callback(download_progress_count,download_progress_length)
                    continue;

                print_log("[=] 다운로드 시작 => "+ fileName)

                if not os.path.exists(path):
                    os.makedirs(path)

                gdrive.download(each_file, path + fileName, quiet=False)
                print_log("[+] 파일 다운로드가 완료 되었습니다. ")
                    
                download_progress_count += 1
                callback(download_progress_count,download_progress_length)
                return 1;
    
        except urllib.error.HTTPError as e:
            print_log("[=] 해당 URL은 스킵되었습니다. : %s" % e)
            download_progress_count += 1
            return 0;
        except Exception as e:
            print_log("[-] Error : %s" % e)
            print_log(traceback.format_exc())
            download_progress_count += 1
            return 0;

def download_count_website(url):

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

