"""
medijob.cc 개원 공고 수집 스크립트
- 공고제목에 '개원' 포함된 활성 공고 수집
- 병원명 기준 중복 제거
- data/master.json 누적 적재 (신규 추가 / 마감 처리)
"""

import requests
import json
import os
import re
from datetime import datetime, timezone, timedelta
from bs4 import BeautifulSoup

# ── 설정 ─────────────────────────────────────────────────
KST = timezone(timedelta(hours=9))
TODAY = datetime.now(KST).strftime('%Y-%m-%d')
DATA_PATH = 'data/master.json'

BASE_URL = 'https://www.medijob.cc'
LIST_URL = (
    BASE_URL + '/rec/cla/sub/rec_cla_108_list_01'
    '?paging=Y&page={page}&rows=30&sidx=recruitJumpDate&sord=DESC'
    '&loginId=pass'
    "&codeStr=%7B%27basis%27%3A+%27MJ006%2CMJ016%2CMJ007%2CMJ035%2CMJ036"
    "%2CMJ017%2CMJ031%2CMJ049%2CMJ043%27%7D"
    '&jobCode=&jobDetailCode=&recruitRegionCode=&recruitRegionGuCode='
    '&companyOrgCode=&recruitKeywordText=%EA%B0%9C%EC%9B%90'
    '&formId=recCla108Form01'
)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Referer': 'https://www.medijob.cc/rec/cla/rec_cla_108',
}

# ── 구-지점 매핑 ──────────────────────────────────────────
GU_MAP = {
    '종로구':'중부지점','중구':'중부지점','용산구':'중부지점','성동구':'중부지점',
    '광진구':'중부지점','동대문구':'중부지점',
    '중랑구':'북부지점','성북구':'북부지점','강북구':'북부지점',
    '도봉구':'북부지점','노원구':'북부지점',
    '은평구':'서부지점','서대문구':'서부지점','마포구':'서부지점',
    '양천구':'남부1지점','구로구':'남부1지점','영등포구':'남부1지점','광명시':'남부1지점',
    '금천구':'남부2지점','동작구':'남부2지점','관악구':'남부2지점',
    '강서구':'일산지점',
    '서초구':'서초지점','강남구':'강남지점',
    '송파구':'강동지점','강동구':'강동지점','하남시':'강동지점',
    '미추홀구':'인천1지점','연수구':'인천1지점','남동구':'인천1지점','옹진군':'인천1지점',
    '부평구':'인천2지점','부천시':'인천2지점',
    '계양구':'인천3지점','서구':'인천3지점','강화군':'인천3지점','김포시':'인천3지점',
    '성남시':'성남지점','수정구':'성남지점','중원구':'성남지점','분당구':'성남지점','광주시':'성남지점',
    '수원시':'수원지점',
    '의정부시':'의정부지점','동두천시':'의정부지점','양주시':'의정부지점',
    '포천시':'의정부지점','연천군':'의정부지점',
    '안양시':'안양지점','과천시':'안양지점','시흥시':'안양지점',
    '군포시':'안양지점','의왕시':'안양지점',
    '평택시':'동탄지점','오산시':'동탄지점','안성시':'동탄지점','화성시':'동탄지점',
    '안산시':'안산지점',
    '고양시':'일산지점','파주시':'일산지점',
    '구리시':'남양주지점','남양주시':'남양주지점','가평군':'남양주지점','양평군':'남양주지점',
    '용인시':'용인지점','이천시':'용인지점',
    '해운대구':'부산4출장소','기장군':'부산4출장소',
    '동래구':'부산2지점','금정구':'부산2지점','연제구':'부산2지점',
    '사하구':'부산3지점','사상구':'부산3지점','양산시':'부산3지점',
    '수성구':'대구1지점','달서구':'대구2지점','달성군':'대구2지점',
    '경산시':'대구3지점','유성구':'대전2지점','세종':'대전2지점',
}

JOB_KEYWORDS = [
    '간호조무사','물리치료사','방사선사','임상병리사','간호사',
    '원무','접수','수납','코디','실장','상담','PA','수술실',
    '도수치료사','한의사','의사','약사','치과위생사','피부관리사','보건',
]


def classify_branch(region: str) -> str:
    if not region:
        return '-'
    for gu, branch in GU_MAP.items():
        if gu in region:
            return branch
    return '-'


def classify_type(hospital: str) -> str:
    if '요양병원' in hospital:
        return '요양병원'
    if '한의원' in hospital or '한방병원' in hospital:
        return '한의원'
    if '의원' in hospital:
        return '의원'
    if '병원' in hospital:
        return '병원'
    return '기타'


def get_sido(region: str) -> str:
    for s in ['서울', '경기', '인천', '부산', '대구', '대전', '광주', '울산']:
        if region.startswith(s):
            return s
    return '기타'


def extract_jobs(title: str) -> list:
    found = []
    for kw in JOB_KEYWORDS:
        if kw in title:
            found.append(kw)
    return found


def fetch_page(page: int) -> list:
    """한 페이지 수집 → rec_li 블록 리스트 반환"""
    url = LIST_URL.format(page=page)
    try:
        res = requests.get(url, headers=HEADERS, timeout=15)
        res.raise_for_status()
    except Exception as e:
        print(f'  [오류] page {page}: {e}')
        return []

    soup = BeautifulSoup(res.text, 'html.parser')
    blocks = soup.select('div.rec_li')
    return blocks


def parse_block(block) -> dict | None:
    """rec_li 블록 파싱 → 공고 dict"""
    hospital = (block.select_one('.rec_li_tit') or {}).get_text(' ', strip=True)
    title    = (block.select_one('.rcTit') or {}).get_text(' ', strip=True)
    rlc2     = (block.select_one('.rlc2') or {}).get_text(' ', strip=True)
    btn_text = (block.select_one('.rec_li_btn') or {}).get_text(' ', strip=True)

    link = block.select_one('a[href*="Seqno"]')
    seqno_match = re.search(r'Seqno=(\d+)', link['href']) if link else None
    seqno = seqno_match.group(1) if seqno_match else ''

    # 공고제목에 '개원' 없으면 스킵
    if '개원' not in title:
        return None

    # 지역 파싱
    rm = re.search(r'([가-힣]{1,6})\s*>\s*([가-힣\s]{1,15}?)(?=\s|$)', rlc2)
    region = f"{rm.group(1).strip()} > {rm.group(2).strip()}" if rm else ''

    # 마감 여부
    is_closed = '마감' in btn_text or '종료' in btn_text

    # 마감일
    if '채용시까지' in btn_text:
        deadline = '채용시까지'
    elif is_closed:
        deadline = '마감'
    else:
        d_match = re.search(r'D-\d+|\d{4}\.\d{2}\.\d{2}', btn_text)
        deadline = d_match.group() if d_match else ''

    # 등록일
    reg_match = re.search(r'\d+일전', btn_text)
    reg_date = reg_match.group() if reg_match else ''

    return {
        'seqno':     seqno,
        'hospital':  hospital,
        'title':     title,
        'region':    region,
        'sido':      get_sido(region),
        'branch':    classify_branch(region),
        'type':      classify_type(hospital),
        'jobs':      extract_jobs(title),
        'deadline':  deadline,
        'reg_date':  reg_date,
        'is_closed': is_closed,
        'url':       f'{BASE_URL}/com/cpn/com_cpn_100_view_02?recruitSeqno={seqno}',
    }


def crawl_all() -> list:
    """전체 페이지 순회 수집"""
    raw = []
    print(f'[{TODAY}] 수집 시작...')
    for page in range(1, 51):
        blocks = fetch_page(page)
        if not blocks:
            print(f'  page {page}: 데이터 없음 → 종료')
            break
        for block in blocks:
            item = parse_block(block)
            if item:
                raw.append(item)
        print(f'  page {page}: {len(blocks)}건 처리 / 개원 누적 {len(raw)}건')
        if len(blocks) < 30:
            break
    print(f'  수집 완료: 원본 {len(raw)}건')
    return raw


def dedup(raw: list) -> list:
    """병원명+지역 기준 중복 제거, 직종 묶기"""
    grouped = {}
    for d in raw:
        key = d['hospital'] + '|' + d['region']
        if key not in grouped:
            grouped[key] = {**d, 'jobs': list(d['jobs']), 'seqnos': [d['seqno']], 'count': 1}
        else:
            grouped[key]['count'] += 1
            grouped[key]['seqnos'].append(d['seqno'])
            grouped[key]['jobs'] += d['jobs']
            if not d['is_closed']:
                grouped[key]['is_closed'] = False
                grouped[key]['deadline'] = d['deadline']
                grouped[key]['reg_date'] = d['reg_date']
    for v in grouped.values():
        v['jobs'] = list(dict.fromkeys(j for j in v['jobs'] if j))  # 순서 유지 dedup
    return list(grouped.values())


def load_master() -> dict:
    """기존 master.json 로드 (없으면 초기화)"""
    if os.path.exists(DATA_PATH):
        with open(DATA_PATH, encoding='utf-8') as f:
            return json.load(f)
    return {'hospitals': {}, 'snapshots': [], 'last_updated': ''}


def save_master(master: dict):
    os.makedirs('data', exist_ok=True)
    with open(DATA_PATH, 'w', encoding='utf-8') as f:
        json.dump(master, f, ensure_ascii=False, indent=2)


def update_master(master: dict, today_data: list) -> dict:
    """
    master 구조:
      hospitals: { 'hospital|region': { ...info, first_seen, last_seen, history[] } }
      snapshots: [ { date, count, hospital_keys[] } ]  ← 날짜별 스냅샷
      last_updated: 'YYYY-MM-DD'
    """
    hospitals = master.get('hospitals', {})
    today_keys = set()

    # 오늘 데이터로 hospitals 업데이트
    for d in today_data:
        key = d['hospital'] + '|' + d['region']
        today_keys.add(key)
        if key not in hospitals:
            # 신규 병원
            hospitals[key] = {
                **d,
                'first_seen': TODAY,
                'last_seen':  TODAY,
                'closed_date': None,
                'status': 'active',
            }
            print(f'  [신규] {d["hospital"]} ({d["region"]})')
        else:
            # 기존 병원 - 정보 갱신
            hospitals[key].update({
                'title':      d['title'],
                'jobs':       d['jobs'],
                'deadline':   d['deadline'],
                'is_closed':  d['is_closed'],
                'last_seen':  TODAY,
                'status':     'active',
                'closed_date': None,
            })

    # 오늘 안 보이는 병원 → 마감 처리
    for key, h in hospitals.items():
        if h['status'] == 'active' and key not in today_keys:
            h['status'] = 'closed'
            h['closed_date'] = TODAY
            print(f'  [마감] {h["hospital"]} ({h["region"]})')

    # 스냅샷 추가
    snapshots = master.get('snapshots', [])
    # 오늘 스냅샷이 이미 있으면 덮어씀
    snapshots = [s for s in snapshots if s['date'] != TODAY]
    snapshots.append({
        'date':  TODAY,
        'count': len(today_data),
        'keys':  list(today_keys),
    })
    # 최근 90일만 유지
    snapshots = sorted(snapshots, key=lambda s: s['date'])[-90:]

    master['hospitals']    = hospitals
    master['snapshots']    = snapshots
    master['last_updated'] = TODAY
    return master


def main():
    # 1. 수집
    raw = crawl_all()
    if not raw:
        print('[경고] 수집된 데이터 없음. 종료.')
        return

    # 2. 중복 제거
    today_data = dedup(raw)
    print(f'  중복제거: {len(raw)}건 → {len(today_data)}개 병원')

    # 3. master 업데이트
    master = load_master()
    master = update_master(master, today_data)

    total   = len(master['hospitals'])
    active  = sum(1 for h in master['hospitals'].values() if h['status'] == 'active')
    closed  = total - active
    print(f'  master 누적: 전체 {total}개 / 활성 {active}개 / 마감 {closed}개')

    # 4. 저장
    save_master(master)
    print(f'  data/master.json 저장 완료')


if __name__ == '__main__':
    main()
