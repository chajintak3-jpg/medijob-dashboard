# 🏥 메디잡 개원병원 현황

medijob.cc에서 개원 공고를 매일 자동 수집하여 GitHub Pages로 배포합니다.

## 구조

```
medijob-deploy/
├── .github/workflows/crawl.yml   ← 매일 오전 8시 자동 실행
├── scraper/crawl.py              ← 수집 스크립트
├── data/master.json              ← 누적 데이터 (자동 갱신)
└── index.html                    ← 배포 페이지
```

## 데이터 구조

- **수집 기준**: 공고제목에 "개원" 포함된 공고
- **중복 제거**: 병원명+지역 기준 1개로 합침
- **누적 적재**: 신규 병원 추가 / 마감 병원 이력 보존
- **자동 갱신**: 매일 오전 8시 KST GitHub Actions 실행

## GitHub 세팅 방법

### 1. Repository 생성
- GitHub에서 새 repository 생성
- 이름 예: `medijob-dashboard`
- **Public** 으로 설정 (GitHub Pages 무료 사용)

### 2. 파일 업로드
이 폴더 전체를 repository에 push

```bash
git init
git add .
git commit -m "초기 세팅"
git remote add origin https://github.com/[계정명]/medijob-dashboard.git
git push -u origin main
```

### 3. GitHub Pages 활성화
- Repository → **Settings** → **Pages**
- Source: **Deploy from a branch**
- Branch: **main** / **/ (root)**
- Save

### 4. Actions 권한 설정
- Repository → **Settings** → **Actions** → **General**
- Workflow permissions: **Read and write permissions** 체크
- Save

### 5. 첫 번째 수동 실행
- Repository → **Actions** → **메디잡 개원공고 수집**
- **Run workflow** 버튼 클릭

### 6. 접속 URL
```
https://[계정명].github.io/medijob-dashboard/
```

## 자동 갱신 스케줄

매일 오전 8시 KST 자동 실행 (cron: `0 23 * * *` UTC 기준)

수동 실행도 가능: Actions 탭 → Run workflow
