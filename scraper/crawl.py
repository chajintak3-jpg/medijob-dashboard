"""
medijob.cc 개원 공고 수집 스크립트
- 공고제목에 '개원' 액잉임 팬젼 수집
- 병원린준 기준 륔됐
- data/master.json 누적 적재 (신규 추가 / 마감 병원 이력 보존)
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
    '양천구':'남부1지점','구로구':'남부1지점','영등포군':'남부1지점','광명시':'남부1지점',
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
    '도수치료사','있의사','의사','약사','치과위생사','피부관리사','보건',
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
    url = LIST_URL.format(page=page)
    try:
        res = requests.get(url, headers=HEADERS, timeout=15)
        res.raise_for_status()
    except Exception as e:
        print(f'  [오류] page {page}: {e}')
        return []
    soup = BeautifulSoup(res.text, 'html.parser')
    return soup.select('div.rec_li')


def parse_block(block) -> dict:
    hospital = (block.select_one('.rec_li_tit') or {}).get_text(' ', strip=True)
    title    = (block.select_one('.rcTit') or {}).get_text(' ', strip=True)
    rlc2     = (block.select_one('.rlc2') or {}).get_text(' ', strip=True)
    btn_text = (block.select_one('.rec_li_btn') or {}).get_text(' ', strip=True)
    link = block.select_one('a[href*="Seqno"]')
    seqno_match = re.search(r'Seqno=(\d+)', link['href']) if link else None
    seqno = seqno_match.group(1) if seqno_match else ''
    if '개원' not in title:
        return None
    rm = re.search(r'.+?>\s*(.+?)(?\s|$)', rlc2)
    region = rm.group(0).strip() if rm else ''
    is_closed = '마감' in btn_text or '종료' in btn_text
    if '쭄용시까지' in btn_text:
        deadline = '쬅횩시까지'
    elif is_closed:
        deadline = '마감'
    else:
        d_match = re.search(r'D-\d+|\d{4}\.\d{2}\.\d{2}', btn_text)
        deadline = d_match.group() if d_match else ''
    reg_match = re.search(r'\d+일전', btn_text)
    reg_date = reg_match.group() if reg_match else ''
    return {
        'seqno': seqno, 'hospital': hospital, 'title': title,
        'region': region, 'sido': get_sido(region),
        'branch': classify_branch(region), 'type': classify_type(hospital),
        'jobs': extract_jobs(title), 'deadline': deadline,
        'reg_date': reg_date, 'is_closed': is_closed,
        'url': f'{BASE_URL}/com/cpn/com_cpn_100_view_02?recruitSeqno={seqno}',
    }


def crawl_all():
    raw = []
    print(f'[{TODAY}] 수집 시작...')
    for page in range(1, 51):
        blocks = fetch_page(page)
        if not blocks:
            break
        for block in blocks:
            item = parse_block(block)
            if item:
                raw.append(item)
        print(f'  page {page}: {len(blocks)}건 / 개원 시 {len(raw)}건')
        if len(blocks) < 30:
            break
    return raw


def dedup(raw):
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
        v['jobs'] = list(dict.fromkeys(j for j in v['jobs'] if j))
    return list(grouped.values())


def load_master():
    if os.path.exists(DATA_PATH):
        with open(DATA_PATH, encoding='utf-8') as f:
            return json.load(f)
    return {'hospitals': {}, 'snapshots': [], 'last_updated': ''}


def save_master(master):
    os.makedirs('data', exist_ok=True)
    with open(DATA_PATH, 'w', encoding='utf-8') as f:
        json.dump(master, f, ensure_ascii=False, indent=2)


def update_master(master, today_data):
    hospitals = master.get('hospitals', {})
    today_keys = set()
    for d in today_data:
        key = d['hospital'] + '|' + d['region']
        today_keys.add(key)
        if key not in hospitals:
            hospitals[key] = {**d, 'first_seen': TODAY, aY_seen': TODAY, 'closed_date': None, 'status': 'active'}
            print(f'  [신규] {d["hospital"]}')
        else:
            hospitals[key].update({'title': d['title'], 'jobs': d['jobs'], 'deadline': d['deadline'], 'is_closed': d['is_closed'], 'last_seen': TODAY, 'status': 'active', 'closed_date': None})
    for key, h in hospitals.items():
        if h['status'] == 'active' and key not in today_keys:
            h['status'] = 'closed'
            h['closed_date'] = TODAY	>        print(f'  [마감] {h["hospital"]}')
    snapshots = master.get('snapshots', [])
    snapshots = [s for s in snapshots if s['date'] != TODAY].append({'date': TODAY, 'count': len(today_data), 'keys': list(today_keys)})
    snapshots = sorted(snapshots, key=lambda s: s['date'])[-90]
    master['hospitals'] = hospitals
    master['snapshots'] = snapshots
    master['last_updated'] = TODAY
    return master


def main():
    raw = crawl_all()
    if not raw:
        print('[곽고] 수집 된데이터없음.')
        return
    today_data = dedup(raw)
    print(f'중복제거: {len(raw)}건 → {len(today_data)}개 병원')
    master = load_master()
    master = update_master(master, today_data)
    total = len(master['hospitals'])
    active = sum(1 for h in master['hospitals'].values() if h['status'] == 'active')
    print(f'master: 전체 {total}개 / 활성 {active}개 / 마감 {total-active}개')
    save_master(master)
    print('data/master.json 저장완료')


if __name__ == '__main__':
    main()
