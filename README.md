# SentinelPose

CCTV 이상행동 탐지 + RAG 매뉴얼 연동 포트폴리오 프로젝트.

2-Stage 아키텍처:
1. YOLOv8-Pose(+ByteTrack)로 사람 키포인트 시퀀스 추출
2. 키포인트 결측 보간 + BBox 상대좌표 정규화
3. 1D-CNN / GRU 경량 분류기로 이상행동(폭행/실신/침입) 분류
4. 이상 이벤트 발생 시 RAG 벡터DB 검색으로 대응 매뉴얼 반환

데이터 출처: AI Hub "이상행동 CCTV 영상" (NIA2019 Database)

## 프로젝트 구조

```
src/sentinelpose/
  data/
    xml_parser.py    # NIA2019 XML 라벨 파서
    trim.py           # 액션 구간 기준 FFmpeg 트리밍
    preprocess.py      # 키포인트 결측 보간 + BBox 정규화
  models/
    classifier.py       # 1D-CNN / GRU 분류기 (PyTorch)
tests/                    # pytest 단위 테스트
```

## 개발 진행 상황

작업 일지는 [WORKLOG.md](WORKLOG.md) 참고.

## 테스트

```
pip install -r requirements.txt
pytest
```
