# JNU Research SSD FTL

MQSim 기반 SSD 시뮬레이터에 여러 FTL(Flash Translation Layer) 매핑 정책을 구현하고,
동일한 워크로드에서 성능/오버헤드/메모리 특성을 비교하기 위한 연구 프로젝트입니다.

## 프로젝트 개요

- 기본 시뮬레이터: `MQSim/` (FAST 2018 MQSim 코드베이스 기반)
- 연구 대상: DFTL(기준), GFTL, CCFTL, COMPRESSION FTL
- 주요 목표: 매핑 방식에 따른 응답시간, IOPS, 매핑 오버헤드, DRAM 추정량 비교
- 설계 문서: `design/FTL_Design_Spec.md`

## 저장소 구조

- `MQSim/`: 시뮬레이터 소스, 빌드 파일, SSD/워크로드 XML, trace 파일
- `design/`: FTL 설계 사양 문서
- `results/`: 실험 산출물(CSV/XLSX/PNG) 및 결과 생성 스크립트
- `log/`: 작업 로그

## 구현된 FTL

### 1) GFTL (Group-level FTL)
- 구현: `MQSim/src/ssd/Address_Mapping_Unit_GFTL.{h,cpp}`
- 특성: 논리 페이지를 그룹 단위로 묶어 매핑 테이블 크기를 절감

### 2) CCFTL (Continuity Compressed FTL)
- 구현: `MQSim/src/ssd/Address_Mapping_Unit_CCFTL.{h,cpp}`
- 특성: 연속 구간 매핑 압축(Run-length 계열)으로 순차 접근 효율 개선

### 3) COMPRESSION FTL
- 구현: `MQSim/src/ssd/Address_Mapping_Unit_Compression.{h,cpp}`
- 특성: 그룹/델타 기반 압축으로 준순차 패턴 대응

FTL 선택 분기(디바이스 생성 시): `MQSim/src/exec/SSD_Device.cpp`

## 설정 파일 (예시)

- SSD 설정
  - DFTL: `MQSim/ssdconfig.xml`
  - GFTL: `MQSim/ssdconfig-gftl.xml`
  - CCFTL: `MQSim/ssdconfig-ccftl.xml`
  - COMPRESSION: `MQSim/ssdconfig-compression.xml`

- 워크로드(기본 비교)
  - DFTL: `MQSim/workload-dftl.xml`
  - GFTL: `MQSim/workload-gftl.xml`
  - CCFTL: `MQSim/workload-ccftl.xml`
  - COMPRESSION: `MQSim/workload-compression.xml`

- 추가 시나리오(갭/핫라이트)
  - `MQSim/workload-gap-ccftl.xml`
  - `MQSim/workload-gap-compression.xml`
  - `MQSim/workload-hotwrite-ccftl.xml`
  - `MQSim/workload-hotwrite-compression.xml`

## 빌드 및 실행

### Linux

```bash
cd MQSim
make
./MQSim -i ssdconfig-gftl.xml -w workload-gftl.xml
```

### Windows

1. `MQSim/MQSim.sln`을 Visual Studio(2017+)에서 엽니다.
2. Configuration을 `Release`로 설정합니다.
3. 빌드 후 실행 파일(`MQSim.exe`)을 사용해 아래와 같이 실행합니다.

```powershell
MQSim.exe -i ssdconfig-gftl.xml -w workload-gftl.xml
```

## 결과 파일 및 분석

- 대표 요약 결과: `results/ftl_summary_results.csv`
- 보고서/시각화 생성 스크립트: `results/generate_ftl_report.py`
- CCFTL vs COMPRESSION 갭 스윕: `results/sweep_ccftl_compression_gap.py`
- 주요 그래프
  - `results/ftl_comparison_overview.png`
  - `results/ccftl_vs_compression_gap_heatmap.png`

## 재현(예시 워크플로우)

1. `MQSim/`에서 대상 FTL별로 시뮬레이션 실행
2. 생성된 `*_scenario_1.xml` 결과 확인
3. 루트에서 분석 스크립트 실행

```bash
python results/generate_ftl_report.py
```

4. `results/` 아래 CSV/XLSX/PNG 산출물 비교

## 참고

- MQSim 원문/사용법: `MQSim/README.md`
- 본 프로젝트 FTL 설계 문서: `design/FTL_Design_Spec.md`
- Code editor: ai-enterprise
- 관리자: 이형민
