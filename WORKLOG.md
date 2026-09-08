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

### 완료 — 방침 결정 및 전체 트리밍 실행

18. **falldown 클래스 출처 결정: assault와 섞지 않고 swoon만 사용**
    - assault의 person_2 falldown(맞아서 넘어짐)과 swoon의 falldown/totter(스스로 실신)는 동작 발생 원인이 달라 동작 패턴도 다를 수 있다고 판단
    - swoon만으로 이미 78개(zip 2개 합산) 확보되어 굳이 섞을 필요가 없어짐 → **분리 확정**. assault의 falldown은 assault 클래스 내부 액션으로만 남기고 별도 클래스로 재사용하지 않음
    - git 관리는 사용자가 직접 하기로 함 (에이전트는 이후 커밋 실행하지 않음)

19. **`scripts/build_clips.py` 작성 — 3개 클래스 전체 트리밍 실행**
    - assault(inside_croki_01) / falldown(swoon inside_croki_01 + outsidedoor_01) / intrusion(trespass outsidedoor_01 + outsidedoor_04) 총 6개 소스 폴더를 파싱해서 한 번에 트리밍
    - 결과: **483/483개 클립 전부 생성 성공** (assault 337, falldown 78, intrusion 68)
    - 용량: 원본 로컬 27.5GB → 트리밍 클립 **총 35MB** (`data/trimmed/`, 480p, git에는 안 올라감 — .gitignore 처리됨)

## 2026-09-08 (GPU 단계)

### 완료 — YOLOv8-Pose 키포인트 추출

20. **GPU 환경 세팅**: torch가 CPU 전용 빌드로 깔려있어 CUDA 빌드(torch 2.6.0+cu124, torchvision 0.21.0+cu124)로 재설치. ultralytics 설치. RTX 4060 Ti 정상 인식(드라이버 CUDA 13.2)
    - Windows OpenMP 충돌(`OMP: Error #15`) 발생 → `KMP_DUPLICATE_LIB_OK=TRUE` 환경변수로 우회

21. **assault에서 person_2 falldown(54개) 제외 확정** — 337 → 283개 클립만 추출 대상으로 사용 (falldown 클래스와의 라벨 혼동 방지, WORKLOG #18과 일관된 결정)

22. **`src/sentinelpose/data/extract_keypoints.py` 작성 — 클립 내 다중 인물 처리**
    - 클립 안에 2명 이상 잡힐 수 있어(실측 57.8%), **클립 내 가장 오래 지속적으로 추적된 track**을 라벨 대상 인물로 간주하는 근사 휴리스틱 채택 (세션 전체 트래킹+XML 위치참조 매칭이 더 정교하지만 포트폴리오 스코프에서는 과함)
    - 1차 시도(`yolov8n-pose`, 기본 conf): 전체 429개 중 **38개(8.9%) 완전 검출 실패** — 특히 falldown 16.7%, intrusion 35.3%로 편중. 원인: 쓰러진 자세/담 넘는 자세/야간 장면이 COCO-pose 학습 분포에서 벗어나 nano 모델이 취약
    - 2차 시도(`yolov8x-pose`, conf=0.15로 완화): 실패 **23개(5.4%)로 개선** (falldown 5.1%, intrusion 14.7%, assault만 소폭 증가 1→9개이나 절대량 작음)
    - 최종 사용 가능 표본: **assault 274 / falldown 74 / intrusion 58 = 총 406개**
    - 결과물: `data/keypoints/<class>/*.npy` (T,17,3) + `manifest.csv` (클립별 프레임수/사용된 track_id/최대 동시 검출 인원). 전체 용량 7MB
    - `.gitignore`에 `*.pt`(YOLO 사전학습 가중치, 133MB) 추가

23. **`preprocess.py`에 `to_fixed_length()` 추가 + `scripts/build_dataset.py` 작성**
    - 클립마다 길이가 29~90프레임으로 제각각이라, 모델 입력 스펙(30프레임)에 맞춤: 길면 중앙 crop, 짧으면 가장자리 프레임 반복 패딩
    - 단위테스트 3개 추가 (통과/중앙크롭/가장자리패딩), 전체 19개 테스트 통과
    - 검출 실패 23개 제외 → 406개에 보간+정규화+길이고정 적용 → `(N, 34, 30)` 텐서로 flatten (conf 채널은 보간 단계에서 이미 제거되어 채널=17*2=34)
    - 결과: `data/dataset.npz` (X: (406,34,30), y: (406,), classes: [assault, falldown, intrusion]) — assault 274 / falldown 74 / intrusion 58, manifest 집계와 정확히 일치 확인

24. **`scripts/train.py` — TemporalCNN/TemporalGRU 학습 + 평가 완료**
    - stratified split(train 284/val 61/test 61), 클래스 불균형 대응 위해 CrossEntropyLoss에 class weight 적용
    - 60 epoch 학습, GPU(RTX 4060 Ti)로 **총 5.7초** 소요 (예상했던 대로 초경량)
    - 결과: TemporalCNN val 0.770/test 0.721, **TemporalGRU val 0.787/test 0.787** (GRU가 근소 우위)
    - GRU Confusion Matrix(test n=61): assault 39/41 정답, falldown은 assault로 오분류 5건(11개 중) — WORKLOG #18에서 우려했던 "낙상 동작이 assault의 밀치기 계열과 헷갈릴 수 있음" 우려가 실제로 일부 나타남. intrusion은 4/9 정답으로 가장 약함(표본 58개로 가장 적음)
    - 모델 가중치 `outputs/*.pt`(git 제외), Confusion Matrix `outputs/*_confusion_matrix.csv` 저장

### 완료 — 표본 증량 시도 (2차)

25. **성능 78.7% 평가**: 테스트셋 다수 클래스(assault) 베이스라인이 이미 67.2%라서, GRU의 실질 개선폭은 11.5%p뿐이라는 걸 확인. falldown/intrusion recall은 44~45%로 약함 → 표본 증량을 시도해보기로 결정
26. **표본 증량 우선순위 논의**: assault는 이미 39/41(95%) 정답이라 더 늘려도 개선 여지가 거의 없음 → **intrusion(가장 약한 클래스)부터 우선 테스트**하기로 결정 (assault를 먼저 테스트하면 "효과 없음"이라는 잘못된 결론에 이를 위험이 있음)
27. **swoon "indoor" zip 시도 → 중복 데이터로 판명, 폐기**
    - swoon 폴더에 inside_croki/indoor/outdoor 3개 그룹이 있어 안 써본 "insidedoor_01.zip"(29GB) 추가 시도
    - 압축 해제해보니 세션명(101-1~101-5)이 기존 inside_croki_01과 완전히 겹침. XML을 diff해보니 **byte 단위로 완전히 동일** — 같은 사건을 다른 인코딩(용량만 267MB→783MB로 다름)으로 재포장한 중복 데이터였음
    - **교훈**: zip 이름이 달라도(inside_croki vs indoor vs outdoor) 실제로는 같은 세션ID가 겹칠 수 있으니, 새 zip 받을 때마다 세션명 중복 여부를 먼저 확인해야 함. 중복인 채로 학습에 섞으면 train/test 데이터 누수 위험
    - 해당 zip/추출폴더 삭제 완료. swoon은 place02/03/04 세 장소만 존재하는 것으로 보여 이 데이터셋 내에서는 추가 증량 여지가 낮다고 판단, **trespass(intrusion) 쪽에 증량 노력 집중하기로 함**

28. **trespass `outsidedoor_02.zip`(30.7GB) 추가 확보 — 중복 없음 확인 후 진행**
    - 처리 전 기존 세션명(23개)과 겹치는지 먼저 체크 → **겹침 0개, 신규 13개**(146-6, 147-1~6, 148-1~6) 확인 후 진행 (WORKLOG #27 교훈 적용)
    - action: pulling 18 / walking 7 / climbwall 6 = 31개. `cam01+spring` 선택 추출 → 26GB→7.1GB, 원본 삭제
    - **intrusion 합산(zip 3개)**: climbwall 26 / pulling 54 / walking 18 / running 1 = **총 99개** (climbwall+pulling만 80개, 기존 68→대폭 증가). intrusion 폴더 총 20GB

29. **`build_clips.py`에 intrusion 소스(`outsidedoor_02`) 추가 후 재트리밍**: assault 337 + falldown 78 + intrusion 99 = **514개 클립** 생성 완료

30. **키포인트 재추출 중 CUDA 크래시 발생 → 재시도로 해결**
    - 사용자가 다른 GPU 작업과 동시 실행 중 VRAM 점유 상태에서 `RuntimeError: CUDA error: illegal memory access` 발생 (283개 중 150개 처리 후 중단)
    - GPU 메모리 여유 확인(`nvidia-smi`) 후 재시도로 정상 처리됨 — **앞으로 GPU 작업 전엔 항상 여유 메모리 먼저 확인**

31. **swoon `insidedoor_03.zip`(31GB) 추가 확보 — 중복 없음 확인 후 진행**
    - 기존 22개 세션과 대조 → **겹침 0개, 신규 8개**(105-2~6, 116-1~3)
    - action: falldown 16 / totter 7 = 23개. `cam01+spring` 선택 추출 → 31GB→2.7GB, 원본 삭제
    - **swoon 합산(zip 3개)**: falldown 63 / totter 38 = **총 101개** (기존 78→101). swoon 폴더 총 13GB
    - 주의: 이 zip은 514개 클립 재트리밍(#29) **이후**에 받은 것이라, 현재 GPU에서 돌아가는 키포인트 추출은 falldown 78개 기준 데이터임 — swoon 증량분(23개)은 별도로 다시 트리밍+추출 필요

32. **`extract_keypoints.py` 증분 처리로 개선**: 이미 처리된(.npy + manifest 존재) 클립은 스킵하고 새 클립만 GPU로 처리하도록 변경. 데이터를 조금씩 계속 추가하는 패턴이 반복될 것 같아 매번 전체 재처리하던 비효율을 제거

33. **키포인트 추출 중 CUDA illegal memory access 재발** — GPU 메모리 확인(`nvidia-smi`) 후 재시도로 해결. 이번엔 증분 처리 덕에 재시도 비용이 낮았음

34. **intrusion·falldown 최종 규모**: intrusion 99개(usable 84), falldown 101개(usable 95) 확보. `build_dataset.py` 재실행 → **총 453개**(assault 274/falldown 95/intrusion 84)

35. **표본 증량 후 재학습 → assault↔intrusion 신규 혼동 발견, "pulling" 원인 가설 검증**
    - 453개로 재학습 시 전체 정확도가 오히려 하락(baseline 대비 +11.5%p→+7.3%p로 축소). assault가 intrusion으로 오분류되는 사례 신규 발생
    - 가설: intrusion의 pulling(문 강제개방)과 assault의 pulling(몸싸움 중 잡아당김)이 **액션 이름이 아니라 실제 관절 움직임 자체가 유사**해서 모델이 구분 못함 (모델은 액션명을 보지 않고 좌표만 봄 — 최초 가설이었던 "이름 충돌"은 부정확한 표현이었고 "동작 유사성"이 정확한 원인)
    - 검증 실험: intrusion에서 pulling 제외(453→403개, intrusion 84→34개) 후 재학습 → assault recall은 회복(78%→85%)했지만 intrusion 표본이 34개(테스트 5개)로 붕괴해 baseline 대비 이득이 더 낮아짐(+5.0%p) → **가설은 지지되었으나 이 방식의 "해결"은 순손실로 판단, pulling 포함 버전으로 원복**

36. **`train.py`에 랜덤 시드 고정 누락 발견 — 심각한 재현성 문제였음**
    - 같은 데이터로 재학습할 때마다 결과가 67.6%→75.0%→(시드 고정 후) 67.6%/70.6%로 요동침. 원인은 stratified split만 시드 고정되어 있고 모델 초기화/학습 자체는 고정 안 됨
    - `torch.manual_seed()` + `torch.cuda.manual_seed_all()` 추가 → 동일 설정 2회 실행 결과가 완전히 일치함을 확인 (재현성 확보)
    - **교훈**: 지금까지 봤던 여러 "표본 늘렸더니 성능이 이랬다저랬다" 결과 중 일부는 실제 데이터 효과가 아니라 이 재현성 버그로 인한 노이즈였을 가능성 있음 — 이후 모든 성능 비교는 이 시드 고정 이후 수치만 신뢰할 것

### 최종 확정 수치 (2026-09-08, 시드 고정 이후)
- 데이터: assault 274 / falldown 95 / intrusion 84 = **453개**
- TemporalGRU: val 77.9% / **test 70.6%** (baseline 60.3% 대비 **+10.3%p**)
- Confusion Matrix(test n=68): assault 36/41, falldown 8/14, intrusion 4/13

### 표본 증량 관련 최종 판단
- **지금 규모(453개)에서 추가 증량은 불필요하다고 결론**: 늘릴 때마다 예상 못 한 부작용(swoon 중복 데이터, assault↔intrusion 신규 혼동)이 반복됐고, "더 늘리면 더 좋아진다"는 보장이 없음을 두 차례 확인함
- assault↔intrusion(pulling) 혼동은 데이터 양의 문제가 아니라 **포즈 정보만으로는 원천적으로 구분이 애매한 케이스**(관절 움직임 자체가 유사)로 보임 → 포트폴리오에는 이를 "정직한 한계"로 문서화하는 방향으로 진행

## 2026-09-09 — Day6: 실시간 통합 파이프라인

37. **`src/sentinelpose/realtime.py` 작성 — YOLOv8 tracker + 분류기 스트리밍 통합**
    - track별로 최근 30프레임 키포인트를 버퍼링, 버퍼가 차면 매 프레임 분류기 실행
    - 480p 60초 테스트 클립(swoon 101-1 세션, 실제 이벤트 구간 포함) 기준: **FPS 40.71, pose 평균 23.8ms/프레임, 분류기 평균 0.77ms/프레임** — 분류기 자체는 사실상 오버헤드 없음, 병목은 포즈 추정

38. **중대 결함 발견: "정상" 클래스가 없어 평상시에도 강제로 이상행동 판정**
    - 3클래스(assault/falldown/intrusion) 모델로 실시간 테스트한 결과, **평범하게 걷는 구간에서도 assault를 59% 확신도로 예측**, 심지어 **실제 falldown 이벤트 구간에서도 assault를 90%+로 잘못 예측**
    - 원인: (1) 학습 클립은 전부 액션에 정확히 맞춰 트리밍된 이상적 조각이라 실전의 "애매하게 걸친 슬라이딩 윈도우"와 분포가 다름 (2) "정상" 클래스 자체가 없어 모델이 3개 중 하나를 강제로 골라야 함 (3) assault가 학습 데이터 60%를 차지해 애매하면 assault로 쏠림
    - 사용자 지적: 이 문제를 안 고치면 Day7(RAG)이 무의미해짐(정상 상황에서도 계속 오탐 경보) → **필수 작업으로 격상**

39. **`scripts/build_normal_clips.py` 작성 — 정상(normal) 클래스 데이터 확보**
    - 추가 다운로드 없이 기존 원본 세션 영상만 사용: XML에 라벨된 모든 action 구간(±30프레임 마진)을 점유 구간으로 표시하고, 나머지 빈 구간에서 30프레임 윈도우를 90프레임 간격으로 세션당 최대 4개까지 샘플링
    - 80개 세션에서 **320개 정상 클립** 확보 (원본 재사용이라 다운로드 시간 0)
    - 키포인트 추출(GPU, 증분처리 — 기존 3클래스는 캐시 재사용, 신규 320개만 처리) → 검출 실패율이 다른 클래스보다 높음(사람이 아예 프레임 밖에 있는 구간 포함되어 있어 예상된 현상), **usable 191개**

40. **4클래스(assault/falldown/intrusion/normal) 재학습**
    - 데이터: assault 274 / falldown 95 / intrusion 84 / normal 191 = **총 644개**
    - TemporalGRU: val 67.0% / test 61.9% (n=97). 다수 클래스 baseline이 4클래스라 42.3%로 낮아져서, **baseline 대비 실질 이득은 +19.6%p로 오히려 역대 최고** (숫자만 보면 낮아 보이지만 실제로는 가장 좋은 모델)

41. **실시간 데모 재검증 — 문제 해결 확인**
    - 같은 60초 테스트 클립으로 재실행: 평상시 구간에서 assault(0.371)와 normal(0.367)이 거의 동률로 균형잡힘 (이전 0.59 vs 0.26)
    - **실제 falldown 이벤트 구간(frame 768~1068)에서 이제 "falldown"을 0.6 안팎으로 꾸준히 정확하게 예측** (이전엔 이 구간에서도 계속 assault 90%+였음) — 핵심 결함 해결 확인
    - 남은 한계: 이벤트 시작 직전 전환 구간과 클립 맨 끝부분은 여전히 예측이 흔들림 — 완벽하진 않지만 핵심 오탐 문제는 해결됨

### 완료 — Day7 준비: Qwen3-4B를 Ollama 로컬 서빙으로 세팅

42. **로컬 Qwen 환경 확인**: 이전 프로젝트에서 Hugging Face 캐시에 Qwen3-4B(unsloth bnb-4bit, 3.4GB)가 받아져 있었음. Ollama는 미설치. 전용 conda 환경 `unsloth_env`(transformers, unsloth, torch 2.11+cu130)에서 사용 가능한 상태였음

43. **Ollama 설치 (winget)** + **Qwen3-4B → GGUF 변환 → Ollama 등록**
    - `winget install Ollama.Ollama`로 설치
    - unsloth의 `save_pretrained_gguf()`로 변환 시도 중 이슈 2개 발생 및 해결:
      - **이슈1**: `transformers 5.5.0`의 내부 리팩터링(`revert_weight_conversion`)이 특정 가중치 변환에 대해 `NotImplementedError` 발생 → 안정적인 4.x 최신판(`4.57.6`)으로 다운그레이드하여 해결
      - **이슈2**: bnb-4bit로 이미 양자화된 모델은 GGUF 변환에 필요한 "16bit로 복원"이 불가능(`load_in_4bit=True`로 저장된 모델은 역양자화 정보가 없음) → **원본 16bit 리포지토리(`unsloth/Qwen3-4B`)를 별도로 받아서** 변환. GPU 8GB로는 bf16 4B 모델 로드가 빠듯해 `device_map="cpu"`로 로드(변환 도구인 llama.cpp 자체도 CPU 전용이라 GPU 불필요 작업이었음)
    - 변환 완료: `Qwen3-4B.Q4_K_M.gguf`(2.4GB) + Ollama Modelfile 자동 생성 → `ollama create sentinelpose-qwen`으로 등록 성공
    - 테스트 프롬프트로 정상 응답 확인. 이후 불필요해진 중간 산출물(변환용 16bit 원본 7.6GB + 중복 GGUF 2.4GB) 삭제로 약 10GB 회수
    - **주의**: 등록된 모델은 파인튜닝 안 된 **베이스 Qwen3-4B**임 (첫 프로젝트의 파인튜닝된 adapter는 이 캐시에 없었음 — adapter_config.json 자체가 존재하지 않는 스냅샷이었음). GuardianEye의 사고 리포트 생성 용도로는 베이스 모델로 충분하다고 판단하고 진행

### 완료 — Day7: RAG 연동

44. **대응 매뉴얼 작성 (`data/manuals/{assault,falldown,intrusion}.md`)**
    - 실제 공개된 "관제 담당자용 실시간 대응 매뉴얼"은 못 찾음(검색 결과는 대부분 "피해자가 사후에 취할 법적 절차" 위주 — 실시간 보안 대응 매뉴얼은 각 시설 내부 문서라 비공개인 것으로 판단)
    - 대신 실제 검색으로 확인한 절차 요소(112/119 신고, CCTV 증거 보전, 진단서 등)를 반영해 직접 작성. 클래스당 "즉시 대응/신고 절차/사후 조치" 3섹션 구조로 통일

45. **`src/sentinelpose/rag.py` 작성 — 경량 RAG 파이프라인**
    - 문서 수가 적어(9개 청크) 별도 벡터DB 없이 `sentence-transformers`(한국어 모델 `jhgan/ko-sroberta-multitask`) 임베딩 + numpy 코사인 유사도로 직접 구현
    - `retrieve_manual()`: 감지된 이벤트의 class_label로 먼저 필터링 후 검색 — 다른 클래스 매뉴얼이 섞여 나오는 것 방지
    - `generate_report()`: 검색된 매뉴얼 + 이벤트 메타데이터를 Ollama(`sentinelpose-qwen`)에 프롬프트로 넣어 관제 담당자용 사고 리포트 생성. Qwen3의 `<think>` 추론 블록은 정규식으로 제거해 최종 리포트만 남김
    - 설치 중 `sentence-transformers` import가 `torchaudio` DLL 로드 실패로 깨짐 → 텍스트 임베딩에 불필요한 `torchaudio` 제거로 해결

46. **`scripts/test_rag.py`로 end-to-end 검증**
    - 이벤트 `{event: falldown, time: ..., location: 지하주차장 B2}` 기준 검색 결과가 전부 falldown 섹션으로 정확히 필터링됨 (유사도 0.42~0.47)
    - Qwen이 검색된 매뉴얼 내용(30초 관찰, 119 신고, 응급조치, 사후 기록)을 실제로 반영한 4문장 리포트를 정상 생성함을 확인
    - 단위테스트 3개 추가(`parse_manual` 섹션 분리, `build_query` 필드 포함/누락 처리) — 전체 22개 테스트 통과

### Day8 설계 논의 (착수는 다음 세션)
- 현재 realtime.py/rag.py는 순수 백엔드(텍스트/CSV 출력)라 시각화 레이어가 별도로 필요하다는 점 확인
- 계획: (1) OpenCV로 원본 영상 프레임에 스켈레톤+박스+라벨을 그린 "주석 영상" 생성 (신규 생성이 아니라 원본 위에 오버레이) (2) 영상 길이만큼 클래스별 색상 타임라인 바 (3) 타임라인 클릭 시 하단에 rag.py의 매뉴얼+Qwen 리포트 카드 표시
- 데모 입력은 매번 업로드 대신 **미리 골라둔 샘플 클립을 드롭다운으로 선택**하는 방식으로 결정 (대용량 원본 업로드 비효율 방지)
- **사용자 요청**: 화면에 표시할 라벨은 내부 클래스명(assault/falldown/intrusion/normal) 대신 **한글(폭행/낙상(실신)/침입/정상)**로 매핑해서 보여줄 것 — Day8 구현 시 반영 필요

### 다음 할 일 (미착수)
- [ ] Day8: Streamlit/Gradio UI 구현 (위 설계대로 — 주석 영상 + 타임라인 + 리포트 카드 + 한글 라벨 매핑)
- [ ] 트리밍 전 원본 영상 중 일부(3~5개)는 Day 6/8 실시간 데모·UI용으로 별도 보존 여부 결정
- [ ] README에 아키텍처 다이어그램, 의사결정 근거, Confusion Matrix, Latency 수치, "정상 클래스 발견-해결" 스토리 정리 (Day9~10)
