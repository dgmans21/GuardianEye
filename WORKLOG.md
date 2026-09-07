# SentinelPose (GuardianEye) 작업 일지

## 2026-09-07

### 완료

1. **AI Hub 다운로드 프로그램 설치 문제 해결**
   - 증상: INNORIX EX 에이전트 설치는 됐는데 계속 "다운로드 프로그램 설치" 화면만 반복
   - 원인: 파이어폭스 브라우저 문제 (로컬 에이전트와의 통신 이슈로 추정) → 크롬으로 전환 후 정상 동작 확인

2. **AI Hub 데이터 실제 구조 파악** (원래 가정과 크게 다름)
   - 전체 규모: "이상행동 CCTV 영상" 총 12개 클래스, 201개 zip, **약 4.85TB** (원래 가정: 11~14GB — 약 350배 차이)
   - zip 내부 구조: 세션 폴더(장소·사건 단위) → `cam01/02/03(카메라 3대) × spring/summer/winter(계절 3종)` 조합 = 세션당 최대 9개 mp4+xml 쌍
   - XML 라벨 구조:
     - 파일 최상단 `<event>`는 트리밍 기준으로 못 씀 (거의 영상 전체를 덮는 넓은 구간)
     - 실제 유효 라벨은 `<object>`(person_1, person_2...)별 `<action><frame start/end>` 세부 구간 — 한 영상에 수십 개의 짧은 액션 인스턴스가 흩어져 있음

3. **클래스 스코프 확정: assault / falldown(실신) / intrusion(침입) 3종**
   - 선정 근거: 관절 움직임 패턴이 서로 뚜렷이 달라야 경량 분류기(1D-CNN/GRU)가 깨끗하게 구분 가능
   - 제외한 후보와 이유:
     - 강도·납치·데이트폭력·주취행동 → assault와 몸싸움 동작 패턴이 겹쳐 오분류 위험
     - 배회(loitering) → 순간 포즈보다 "시간에 걸친 반복 이동 패턴"이 핵심이라 30프레임(1초) 입력 윈도우로 포착 어려움
     - 절도·투기 → 물체와의 상호작용이 핵심이라 포즈 데이터만으로 구분 애매

4. **assault 데이터 선별·정리 완료**
   - `inside_croki_01.zip`(27GB) 다운로드 → 압축 해제
   - 세션별로 `cam01 + spring` 조합 1쌍만 남기고 나머지(다른 카메라 앵글/계절) 삭제
     - 예외: `10-4`는 spring이 없어 winter로 대체, `10-5`는 cam01이 없어 cam02로 대체
   - 결과: **27GB → 3.5GB**, 13개 세션(사건) 확보

5. **assault XML 13개 전수 스캔 — action 타입별 통계**
   - kicking 88 / pushing 79 / falldown 54 / punching 48 / pulling 34 / threaten 26 / throwing 8 → **총 337개 액션 구간**
   - person_2의 falldown이 54개나 확보되어, 별도 실신 데이터를 많이 안 받아도 assault 영상만으로 falldown 클래스 샘플을 상당수 확보 가능하다는 걸 확인

6. **실신(swoon) 데이터 선별·정리 완료**
   - `inside_croki_01.zip`(30GB) 다운로드 완료 확인 (무결성 검사 통과, 190개 파일)
   - 구조: 세션 10개(101-1~101-6, 102-1~102-4), 세션당 `cam01/02/03 × spring/summer/winter` = 9쌍 — assault와 동일 패턴
   - zip을 통째로 안 풀고, `cam01 + spring` 조합만 zip 내부에서 바로 선택 추출 (Python zipfile) — assault보다 빠르고 디스크 부담 적음
   - 결과: **30GB → 3.2GB**, 10개 세션 확보. 원본 zip은 삭제 완료 (재다운로드 10분 이내로 확인되어 보존 불필요 판단)

7. **침입(trespass) 데이터 선별·정리 완료**
   - `outsidedoor_01.zip`(26GB) 다운로드 완료, 무결성 검사 통과 (88개 파일, 11개 세션)
   - 구조: 세션당 `cam01/cam02(카메라 2대) × spring/summer(계절 2종)` = 8개 조합 — assault/swoon과 카메라·계절 개수만 다르고 동일 패턴
   - zip 내부에서 `cam01 + spring` 선택 추출 → **26GB → 5.6GB**, 11개 세션 확보. 원본 zip 삭제 완료

8. **침입 XML 11개 전수 스캔 — 구조가 assault와 근본적으로 다름을 발견**
   - `population: 1` (assault는 2명), 최상단 `<event>`가 **1.4초로 짧고 정확함** (assault는 사실상 영상 전체를 덮어 트리밍 기준으로 못 썼던 것과 대조적) → 침입 클래스는 top-level event를 그대로 트리밍 기준으로 써도 됨
   - 세션이 두 종류로 나뉨: `145-x`(6개, event=trespass01) = **담 넘기(climbwall)** 단일 액션만 존재 / `146-x`(5개, event=trespass03) = **문·게이트 강제 개방(pulling) + 접근(walking)**, climbwall 없음
   - action 합계: pulling 9 / climbwall 6 / walking 5 / running 1 → **총 21개** (assault 337개, 영상당 밀도가 약 1/16 수준)
   - **리스크**: walking 제외하고 의미있는 침입 동작(climbwall+pulling)만 세면 15개뿐이라 assault·falldown 대비 클래스 불균형이 큼 → zip 추가 다운로드하기로 결정

9. **침입 zip 2개째(`outsidedoor_04.zip`, 27.7GB) 추가 확보**
   - 무결성 통과, 12개 세션, 첫 zip보다 밀도 높음: climbwall 14 / pulling 27 / walking 6 = 47개 액션
   - `cam01 + spring` 선택 추출 → **26GB → 6.9GB**. 원본 zip 삭제 완료
   - **합산(zip 2개)**: climbwall 20 / pulling 36 / walking 11 / running 1 → 의미있는 침입 동작(climbwall+pulling) **56개**, walking 포함 68개. 침입 폴더 총 13GB
   - 클래스 불균형이 15개→56개로 크게 개선되어 zip 추가 다운로드는 여기서 종료, 부족분은 필요 시 증강으로 보완하기로 함

10. **실신(swoon) XML 10개 전수 스캔 — 여기도 assault처럼 안전하다고 가정한 게 틀렸음을 확인**
    - "구조가 비슷하니 충분할 것"이라 가정했던 걸 사용자가 지적 → 실제 스캔해보니 falldown 19 / totter 3 = **총 22개**로 침입과 비슷하게 얇음 (assault 337개와 전혀 다름)
    - 완충 요인: assault의 person_2 falldown(54개)과 합치면 falldown 클래스 총 73개 확보 가능 (단, 맞아서 쓰러짐 vs 스스로 실신은 동작 패턴이 다를 수 있어 완전히 안전한 가정은 아님)
    - 결정: swoon 순수 표본을 늘리기 위해 **outdoor 계열 zip 1개 추가 확보하기로 결정** (기존 inside_croki가 실내 위주라 outdoor로 환경 다양성도 함께 확보)

11. **swoon outdoor zip(29GB) 추가 확보 완료**
    - 무결성 통과, 96개 파일, 12개 세션(100-1~100-6, 103-1~103-6)
    - inside_croki보다 밀도 훨씬 높음: falldown 28 / totter 28 = 56개
    - `cam01 + spring` 선택 추출 → **29GB → 6.9GB**. 원본 zip 삭제 완료
    - **swoon 합산(zip 2개)**: falldown 47 / totter 31 → **총 78개**, swoon 폴더 총 11GB
    - 이제 assault(337) · swoon(78) · intrusion(68) 세 클래스 모두 두 자릿수 이상 확보되어 데이터 수집 단계 종료로 판단

### 로컬 최종 데이터 현황
| 클래스 | 로컬 용량 | 세션 수 | 의미있는 액션 구간 |
|---|---|---|---|
| assault | 3.5GB | 13 | 337 (kicking/pushing/falldown/punching/pulling/threaten/throwing) |
| falldown(swoon) | 11GB | 22 | 78 (falldown 47 + totter 31) |
| intrusion(trespass) | 13GB | 25 | 68 (climbwall 20 + pulling 36 + walking 11 + running 1) |

로컬 원본 총합 약 27.5GB — Kaggle 20GB 제한과는 무관 (실제 업로드분은 키포인트 파일만이라 수십MB 수준으로 예상)

## 2026-09-08 (같은 세션 연속 작업)

### 완료 — 프로젝트 코드 스캐폴딩 (git 저장소 초기화 포함)

12. **git 저장소 초기화 + 프로젝트 구조 세팅**
    - `git init`, `.gitignore`(영상/키포인트 데이터는 저장소에 안 넣음) 작성
    - 구조: `src/sentinelpose/{data, models}/`, `tests/`

13. **XML 파서 (`src/sentinelpose/data/xml_parser.py`)**
    - `ActionSegment`, `EventWindow` dataclass + `parse_annotation_xml`, `parse_dataset`
    - `normalize_object_id()`로 person_1/Person_1/Person/Person01 등 표기 불일치 통일
    - **설계 단순화**: 원래 "assault는 세부 action, trespass는 event" 두 경로가 필요하다고 봤는데, 실제로는 trespass의 climbwall도 `<object><action><frame>`으로 라벨링되어 있어서 **클래스 구분 없이 action 단위 하나의 경로로 통일** 가능함을 확인
    - 실제 assault XML 13개로 스모크 테스트 → 337개 세그먼트 정확히 추출 확인 (이전 수동 스캔 결과와 일치)

14. **FFmpeg 트리밍 (`src/sentinelpose/data/trim.py`)**
    - `compute_clip_window()`: 액션 구간이 모델 입력 최소 길이(30프레임)보다 짧으면 앞뒤로 패딩, 너무 길면(예: 1043프레임짜리 outlier) 중앙 90프레임만 사용, 영상 경계 clamp
    - `trim_clip()` / `trim_segments()`: FFmpeg 서브프로세스 호출, 480p로 다운샘플링하면서 재인코딩 (키프레임 경계 문제로 -c copy 대신 재인코딩 선택)
    - 실제 assault 클립 3개로 트리밍 테스트 → 정상 생성 확인

15. **전처리 함수 (`src/sentinelpose/data/preprocess.py`)**
    - `interpolate_missing_keypoints()`: conf<0.3 → NaN → 선형보간, max_gap(기본 10프레임) 초과 결측은 0 마스킹
    - `normalize_by_bbox()`: 프레임별 관측 키포인트의 min/max로 BBox 잡아 `x_norm=(x-x_min)/w, y_norm=(y-y_min)/h` 정규화

16. **모델 클래스 (`src/sentinelpose/models/classifier.py`)**
    - `TemporalCNN`(1D-CNN), `TemporalGRU`(단일 레이어 GRU) — 입력 shape (B, 51, 30)

17. **단위 테스트 16개 전부 통과** (`pytest`, pytest 9.1.1 설치)
    - preprocess 5개(보간/정규화 경계 케이스 포함), trim 3개(짧은/긴/경계 액션), xml_parser 8개(정규화 파라미터화 6개 + 실제 스키마 파싱 2개)

### 다음 할 일 (미착수)
- [ ] git 첫 커밋
- [ ] YOLOv8-Pose 로컬 추출 파이프라인 (RTX 4060 Ti, 라벨된 사람만 추출) — 유일한 GPU 필요 단계
- [ ] 트리밍 영상 일부(3~5개)는 Day 6/8 실시간 데모·UI용으로 원본 보존
- [ ] 실제 3개 클래스 전체(483개 세그먼트) 트리밍 실행
- [ ] falldown 클래스에서 assault(person_2 falldown)와 swoon(자체 falldown) 출처를 구분하는 서브라벨 유지 여부 결정
