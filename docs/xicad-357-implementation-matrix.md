# xiCAD 357 implementation matrix

> 기준 시점: 2026-07-21. 대상은 `tests/fixtures/xiShortkey.357.key`의 동결된 357개 별칭이다. 이 문서는 구현 계획용 정적 감사 자료이며, 레거시 바이너리의 동작 등가성을 주장하지 않는다.

## 결론

- 전체 357개 중 구조화 Headless 계약은 **52개**, 현재 CAD 변경 MCP가 노출된 명령은 **27개**, CAD 없이 즉시 사용 가능한 명령은 **9개**다.
- 계약 미구현 명령은 **304개**다. 함수 본문이 ZELX/FAS에만 있는 경우가 많아 아래 추정은 확정 의미가 아니라 구현 라우팅 정보다.
- `C:\xicad` 정적 조사: 약 3,018개 파일, DCL 168개, ZELX 30개, FAS 29개, 공개 LSP 12개. “레거시 명령 로드”와 “대화상자 없는 계약/COM 어댑터 검증”은 별개다.

## 범례

| 코드 | 의미 |
|---|---|
| 상태 `LIVE` / `CF` / `CONTRACT` | 실제 CAD 변경 MCP 노출 / CAD-free 즉시 실행 / 구조화 계약만 구현 |
| 상태 `BIN` / `WRAP` / `RENAME` / `EXCL` | 레거시 바이너리만 / 호환 wrapper만 / 함수명 연결만 / 플랫폼 제외 |
| 유형 `CF` / `RO` / `M` / `IO` / `X` | 순수 계산 / CAD 읽기·조회 / CAD 변경 / 문서·파일·외부 I/O / 제외 |
| COM `C/E/G/T/L/D/H/B/P/M/IO` | 계산 / 엔티티 / 기하 / 문자 / 레이어 / 치수 / 해치·테이블 / 블록·XRef / 레이아웃·뷰포트 / 정리·Plot / Documents·파일 |
| 입력 `N/H` | CAD 입력 없음 / 구조화 Headless 입력이 이미 정의됨 |
| 입력 `S/P/D/F/L` + `?` | 선택집합 / 점·수치 / DCL 옵션 / 파일경로 / 레이어·레이아웃. `?`는 레거시 역분석 전 추정 |
| 위험 `L/M/H/C` | 낮음 / 중간 / 높음 / 치명적(삭제·저장·종료 포함) |
| 배치 `0/A… I/X` | 완료 / 계약 보유 어댑터 / 문자 / 레이어 / 치수 / 기하편집 / 블록·레이아웃 / 생성·해치 / 외부 I/O·정리 / 기타 / 제외 |

“COM”은 함수 본문에서 확인한 호출 목록이 아니라 별칭·함수명·섹션에 기반한 **최소 예상 primitive 묶음**이다. `BIN/WRAP/RENAME`의 입력과 위험은 반드시 DCL·프롬프트 캡처 및 Drawing1 fixture로 재확인해야 한다.

## 명령별 매트릭스

### Comm (5)

| 별칭 | 함수 | 상태 | 유형 | COM | 입력 | 위험 | 배치 |
|---|---|---:|---:|---:|---:|---:|---:|
| CT | xiCopyconTents | BIN | M | E | S/P? | M | I |
| DTS | xiDATESTAMP | BIN | M | E | S/P? | M | I |
| FLT | xiFlatten | BIN | M | E | S/P? | M | I |
| GEE | xiGroupEdit | BIN | M | E | S/P? | M | I |
| STL | xiSteal | BIN | IO | IO | S/P? | H | H |

### Open (6)

| 별칭 | 함수 | 상태 | 유형 | COM | 입력 | 위험 | 배치 |
|---|---|---:|---:|---:|---:|---:|---:|
| COM | xiCommandEdit | BIN | IO | IO | F/D? | H | H |
| EXP | xiEXDWG | BIN | IO | IO | F/D? | H | H |
| OL | xiOpenList | BIN | IO | IO | F/D? | H | H |
| ON | xiOpenNext | BIN | IO | IO | F/D? | H | H |
| QQ | xiQuickQuit | BIN | IO | IO | F/D? | C | H |
| STT | xiStart | BIN | M | IO | F/D? | M | H |

### Draw (35)

| 별칭 | 함수 | 상태 | 유형 | COM | 입력 | 위험 | 배치 |
|---|---|---:|---:|---:|---:|---:|---:|
| BE | xiBE | BIN | M | G | P/S/D? | H | G |
| BLI | xiBeamList | BIN | M | G | P/S/D? | H | G |
| BPT | xiBPatt | BIN | M | G | P/S/D? | H | G |
| CALENDAR | xiCalendar | BIN | M | G | P/S/D? | H | G |
| CE | xiCenter | WRAP | M | G | P/S/D? | H | G |
| CEP | xiCenterPoly | BIN | M | G | P/S/D? | H | G |
| CLI | xiColumnList | BIN | M | G | P/S/D? | H | G |
| COL | xiDrawColumn | BIN | M | G | P/S/D? | H | G |
| CW | xiCWALL | BIN | M | G | P/S/D? | H | G |
| D1 | xiDoor1 | BIN | M | G | P/S/D? | H | G |
| D2 | xiDoor2 | BIN | M | G | P/S/D? | H | G |
| D3 | xiDoor3 | BIN | M | G | P/S/D? | H | G |
| DEV | xiDrawExplodedView | BIN | M | G | P/S/D? | H | G |
| EED | xiEED | BIN | M | G | P/S/D? | H | G |
| ELV | xiElevator | BIN | M | G | P/S/D? | H | G |
| EPD | xiEPD | BIN | M | G | P/S/D? | H | G |
| HB | xiHatBDraw | BIN | M | G | P/S/D? | H | G |
| HGRID | xiHeatGrid | BIN | M | G | P/S/D? | H | G |
| HP | xiHatchPoint | BIN | M | G | P/S/D? | H | G |
| INS | xiINSUL | BIN | M | G | P/S/D? | H | G |
| PK | xipk | BIN | M | G | P/S/D? | H | G |
| PZ | xiPartialZoom | BIN | RO | G | P/S/D? | H | G |
| QRC | xiQRcode | BIN | M | G | P/S/D? | H | G |
| SCB | xiScaleBar | BIN | M | G | P/S/D? | H | G |
| STB | xiSTB | BIN | M | G | P/S/D? | H | G |
| STC | xiSTC | BIN | M | G | P/S/D? | H | G |
| STP | xiSTP | BIN | M | G | P/S/D? | H | G |
| TAJ | xiTableWidAj | BIN | M | G | P/S/D? | H | G |
| TRUSS | xitruss | BIN | M | G | P/S/D? | H | G |
| W1 | xiWin1 | BIN | M | G | P/S/D? | H | G |
| W2 | xiWin2 | BIN | M | G | P/S/D? | H | G |
| W3 | xiWin3 | BIN | M | G | P/S/D? | H | G |
| WAL | xiDrawWall | LIVE | M | G | H | H | 0 |
| WO | xiWallOpening | BIN | M | G | P/S/D? | H | G |
| ZIGZAG | xiZIGZAG | BIN | M | G | P/S/D? | H | G |

### Hatch (10)

| 별칭 | 함수 | 상태 | 유형 | COM | 입력 | 위험 | 배치 |
|---|---|---:|---:|---:|---:|---:|---:|
| C2E | xiCad2Excel | BIN | IO | IO | S/D? | H | G |
| E2C | xiExcel2Cad | BIN | IO | IO | S/D? | H | G |
| HC | xiHatchClone | BIN | M | H | S/D? | H | G |
| HEX | xiHatchExport | BIN | IO | IO | S/D? | H | G |
| HM | xiHatchMerge | BIN | M | H | S/D? | H | G |
| HPM | xiMakeHatchPtn | BIN | IO | IO | S/D? | H | G |
| RDS | xiRandomSolid | BIN | M | H | S/D? | H | G |
| SOL | xiSOLID | BIN | M | H | S/D? | H | G |
| TB | xiTable | BIN | M | H | S/D? | H | G |
| TBT | xiTableText | BIN | M | H | S/D? | H | G |

### Cut (14)

| 별칭 | 함수 | 상태 | 유형 | COM | 입력 | 위험 | 배치 |
|---|---|---:|---:|---:|---:|---:|---:|
| BAT | xiBreakAndText | BIN | M | G | S/P? | H | E |
| BB | xiBreakToCurrent | BIN | M | G | S/P? | H | E |
| BBB | xiBreakMulti | WRAP | M | G | S/P? | H | E |
| BRO | xiBreakO | BIN | M | G | S/P? | H | E |
| CB | xiCircleBreak | BIN | M | G | S/P? | H | E |
| CUT | xiCutter | BIN | M | G | S/P? | C | E |
| DTP | xiDivideToPoly | BIN | M | G | S/P? | H | E |
| FE | xiFilletExtend | BIN | M | G | S/P? | H | E |
| FF | xiFilletL | WRAP | M | G | S/P? | H | E |
| FM | xiFilletMulti | BIN | M | G | S/P? | H | E |
| FR | xiFilletRadious | BIN | M | G | S/P? | H | E |
| FT | xiFilletT | BIN | M | G | S/P? | H | E |
| FX | xiFilletX | BIN | M | G | S/P? | H | E |
| XT | xiXT | BIN | M | G | S/P? | H | E |

### Multi (30)

| 별칭 | 함수 | 상태 | 유형 | COM | 입력 | 위험 | 배치 |
|---|---|---:|---:|---:|---:|---:|---:|
| ARD | xiDynamicArr | BIN | M | G | S/P? | H | E |
| ARP | xiArrP | BIN | M | G | S/P? | H | E |
| ARV | xiArrV | BIN | M | G | S/P? | H | E |
| CNL | xiCopyToNewLayer | BIN | M | G | S/P? | H | E |
| CR | xiCopyRotate | BIN | M | G | S/P? | H | E |
| CTL | xiCopyToCLayer | BIN | M | G | S/P? | H | E |
| DAC | xiDivideArcCopy | BIN | M | G | S/P? | H | E |
| DVC | xiDivideCopy | BIN | M | G | S/P? | H | E |
| EXL | xiExtendLine | BIN | M | G | S/P? | H | E |
| JL | xiJoinLine | BIN | M | G | S/P? | H | E |
| MC | xiMCopy | BIN | M | G | S/P? | H | E |
| MLC | xiMlineCv | BIN | M | G | S/P? | H | E |
| MM | xiMeasure | BIN | M | G | S/P? | H | E |
| OA | xiObjectsAlign | BIN | M | G | S/P? | H | E |
| OAA | xiObjectsAlignAngle | BIN | M | G | S/P? | H | E |
| OB | xiofbs | BIN | M | G | S/P? | H | E |
| OE | xiofe | BIN | M | G | S/P? | H | E |
| OI | xiOffsetIntegrate | BIN | M | G | S/P? | H | E |
| OM | xiOffsetMulti | BIN | M | G | S/P? | H | E |
| OO | xiofc | BIN | M | G | S/P? | H | E |
| OT | xiOffsetTolerance | BIN | M | G | S/P? | H | E |
| RC | xiRC | LIVE | M | G | H | H | 0 |
| RDC | xiRandomCopy | BIN | M | G | S/P? | H | E |
| RM | xiRotMulti | BIN | M | G | S/P? | H | E |
| RR | xiRR | RENAME | M | G | S/P? | H | E |
| SB | xiSolidMoveBack | BIN | M | G | S/P? | H | E |
| SM | xiScaleMulti | BIN | M | G | S/P? | H | E |
| SS | xiSCALE | BIN | M | G | S/P? | H | E |
| WQ | xiOffsetAndClose | WRAP | M | G | S/P? | H | E |
| WR | xiWallRecover | BIN | M | G | S/P? | H | E |

### Layer (31)

| 별칭 | 함수 | 상태 | 유형 | COM | 입력 | 위험 | 배치 |
|---|---|---:|---:|---:|---:|---:|---:|
| 1 | xiSelOff | WRAP | M | L | S/L? | M | C |
| 2 | xiSelLayerOn | WRAP | M | L | S/L? | M | C |
| 3 | xiLayeron | WRAP | M | L | S/L? | M | C |
| DOL | xiDraworderByLayer | BIN | M | L | S/L? | M | C |
| ELY | xiEraseLayer | BIN | M | L | S/L? | C | C |
| EOO | xiEntOffOn | BIN | M | L | S/L? | M | C |
| ESF | xiEntSelOff | BIN | M | L | S/L? | M | C |
| ESO | xiEntSelOn | BIN | M | L | S/L? | M | C |
| EW | xiSetCLayer | WRAP | M | L | S/L? | M | C |
| LAM | xiLayerMerge | BIN | M | L | S/L? | M | C |
| LC | xiChangeLayer | BIN | M | L | S/L? | M | C |
| LCC | xiColor2Layer | BIN | M | L | S/L? | M | C |
| LCD | xiColor2Layer2 | BIN | M | L | S/L? | M | C |
| LCO | xiChangeLayerOnly | BIN | M | L | S/L? | M | C |
| LCS | xiLayerChaneSelectObject | BIN | M | L | S/L? | M | C |
| LF | xiSelFreeze | WRAP | M | L | S/L? | M | C |
| LFD | xiLayerFiltersDelete | CONTRACT | M | L | H | M | A |
| LFF | xiSelLayerFreeze | BIN | M | L | S/L? | M | C |
| LFK | xiSelLayerLock | BIN | M | L | S/L? | M | C |
| LK | xiSelLock | BIN | M | L | S/L? | M | C |
| LLC | xiLayerOffColor | BIN | M | L | S/L? | M | C |
| LOC | xiLayerOnColor | WRAP | M | L | S/L? | M | C |
| LOS | xiLayerOnSelect | BIN | M | L | S/L? | M | C |
| LP | xiLayerProperty | BIN | M | L | S/L? | M | C |
| LPP | xiLayerPrefix | LIVE | M | L | H | M | 0 |
| LPS | xiLayerSuffix | LIVE | M | L | H | M | 0 |
| LST | xiLayerList | BIN | RO | L | S/L? | M | C |
| LT | xiLayerThaw | WRAP | M | L | S/L? | M | C |
| LTG | xiLayerOnOffToggle | BIN | M | L | S/L? | M | C |
| LU | xiSelUnLock | BIN | M | L | S/L? | M | C |
| LUK | xiLayerUnlock | BIN | M | L | S/L? | M | C |

### DBox (11)

| 별칭 | 함수 | 상태 | 유형 | COM | 입력 | 위험 | 배치 |
|---|---|---:|---:|---:|---:|---:|---:|
| BMT | xiBoxMoveTool | BIN | M | B | S/P/D? | M | F |
| DAS | xiDyScale | BIN | M | B | S/P/D? | M | F |
| DBC | xiDboxAutoCopy | BIN | M | B | S/P/D? | M | F |
| DBS | xiDboxSort | BIN | M | B | S/P/D? | M | F |
| DFS | xiDboxFindScale | BIN | RO | B | S/P/D? | M | F |
| DSB | xiDimScaleBlock | BIN | M | B | S/P/D? | M | F |
| MDL | xiMakeDwgList | BIN | M | B | S/P/D? | M | F |
| PBS | xiPPlotBox | BIN | M | B | S/P/D? | M | F |
| TN | xiTitleNumbering | BIN | M | B | S/P/D? | M | F |
| TOB | xiObjToBlk | BIN | M | B | S/P/D? | M | F |
| ZR | xiZoomRemember | BIN | M | B | S/P/D? | M | F |

### Area (34)

| 별칭 | 함수 | 상태 | 유형 | COM | 입력 | 위험 | 배치 |
|---|---|---:|---:|---:|---:|---:|---:|
| 00 | xiCalculator | CF | CF | C | N | L | 0 |
| ABC | xiABC | CF | CF | C | N | L | 0 |
| AE | xiAE | BIN | M | C | S/P/D? | M | I |
| AHM | xiMapArea | BIN | M | C | S/P/D? | M | I |
| BA | xiBunArea | BIN | M | C | S/P/D? | M | I |
| CDB | xiCalDistBuilding | BIN | M | C | S/P/D? | M | I |
| CDN | xiCheckDistNorth | BIN | M | C | S/P/D? | M | I |
| COI | xiCommaIns | LIVE | M | C | H | M | 0 |
| COR | xiCommaRem | LIVE | M | C | H | M | 0 |
| DAR | xiDyArea | BIN | M | C | S/P/D? | M | I |
| DEE | xiDrawEnergyElev | BIN | M | C | S/P/D? | M | I |
| DM | xiDistMemory | BIN | M | C | S/P/D? | M | I |
| FFO | xiFindFieldObj | BIN | M | C | S/P/D? | M | I |
| HV | xiHVAREA | BIN | M | C | S/P/D? | M | I |
| HW | xiHWArea | BIN | M | C | S/P/D? | M | I |
| INA | xiIndexNumAdd | LIVE | M | C | H | M | 0 |
| LIS | xiLineSum | LIVE | M | C | H | M | 0 |
| LMA | xiLevelMoveAdd | LIVE | M | C | H | M | 0 |
| LNA | xiLevelNumAdd | LIVE | M | C | H | M | 0 |
| M2 | xim2 | LIVE | M | C | H | M | 0 |
| MAC | xiMakeAreaCenter | BIN | M | C | S/P/D? | M | I |
| MRT | xiMakeRoomTable | BIN | M | C | S/P/D? | M | I |
| ND | xiNumDivide | CF | CF | C | N | L | 0 |
| NP | xiNumBunyangPro | CF | CF | C | N | L | 0 |
| NS | xiNumSubtract | CF | CF | C | N | L | 0 |
| NUC | xiNumberCalulate | LIVE | M | C | H | M | 0 |
| PY | xiPy | LIVE | M | C | H | M | 0 |
| QD | xiQuickDist | LIVE | M | C | H | M | 0 |
| SAR | xiSiteArea | BIN | M | C | S/P/D? | M | I |
| SCA | xiScaleArea | BIN | M | C | S/P/D? | M | I |
| SE | xiSelectSameEntities | BIN | M | C | S/P/D? | M | I |
| SL | xiSLOPE | BIN | M | C | S/P/D? | M | I |
| SPN | xiSumPairNum | LIVE | M | C | H | M | 0 |
| ZAE | xiZareaElev | BIN | M | C | S/P/D? | M | I |

### Txt1 (26)

| 별칭 | 함수 | 상태 | 유형 | COM | 입력 | 위험 | 배치 |
|---|---|---:|---:|---:|---:|---:|---:|
| A2M | xiAtt2Mt | BIN | M | T | S/D? | M | B |
| ABE | xiAttBlkEdit | BIN | M | T | S/D? | M | B |
| CTX | xiCTX | BIN | M | T | S/D? | M | B |
| FAM | xiFindAndMark | BIN | M | T | S/D? | M | B |
| FAR | xiFindReplace | LIVE | M | T | H | M | 0 |
| FTT | xiField2Text | BIN | M | T | S/D? | M | B |
| T2M | xiT2MT | BIN | M | T | S/D? | M | B |
| TAP | xiTextAp | LIVE | M | T | H | M | 0 |
| TC | xiTextCopy | BIN | M | T | S/D? | M | B |
| TD | xiTextDivide | LIVE | M | T | H | M | 0 |
| TE | xiTextEdit | BIN | M | T | S/D? | M | B |
| TEC | xiTextEntryCopy | BIN | M | T | S/D? | M | B |
| TFF | xiTextFrameFix | BIN | M | T | S/D? | M | B |
| TJ | xiTJus | BIN | M | T | S/D? | M | B |
| TM | xiTextMerge | LIVE | M | T | H | M | 0 |
| TO | xiText2Center | BIN | M | T | S/D? | M | B |
| TOA | xiTextOfAlign | BIN | M | T | S/D? | M | B |
| TS | xitsize | LIVE | M | T | H | M | 0 |
| TSA | xiTextStyleALL | BIN | M | T | S/D? | M | B |
| TSE | xiTextSE | BIN | M | T | S/D? | M | B |
| TSH | xiTextShadow | BIN | M | T | S/D? | M | B |
| TSM | xiStyleMerge | BIN | M | T | S/D? | M | B |
| TSO | xiTextStack | BIN | M | T | S/D? | M | B |
| TST | xiTsty | BIN | M | T | S/D? | M | B |
| TSW | xiTextSW | BIN | M | T | S/D? | M | B |
| TW | xiTWid | BIN | M | T | S/D? | M | B |

### Txt2 (14)

| 별칭 | 함수 | 상태 | 유형 | COM | 입력 | 위험 | 배치 |
|---|---|---:|---:|---:|---:|---:|---:|
| DAT | xiDyTitle | BIN | M | T | S/P/D? | M | B |
| LTX | xiLText | BIN | M | T | S/P/D? | M | B |
| NUMC | xiNumInc | LIVE | M | T | H | M | 0 |
| QT | xiCommonTxt | BIN | M | T | S/P/D? | M | B |
| QW | xiQickSpecialChar | BIN | M | T | S/P/D? | M | B |
| TCT | xiTextCount | LIVE | M | T | H | M | 0 |
| TIC | xiAutoNumbering | LIVE | M | T | H | M | 0 |
| TIE | xiPickNumInc | LIVE | M | T | H | M | 0 |
| TII | xiTextIncInput | LIVE | M | T | H | M | 0 |
| TIN | xiTextInEttsInc | LIVE | M | T | H | M | 0 |
| TIP | xiTextPointInc | BIN | M | T | S/P/D? | M | B |
| TOO | xiTextOnObj | BIN | M | T | S/P/D? | M | B |
| TTT | xiTextsToTable | BIN | M | T | S/P/D? | M | B |
| TX | xiTextBox | BIN | M | T | S/P/D? | M | B |

### Dim (26)

| 별칭 | 함수 | 상태 | 유형 | COM | 입력 | 위험 | 배치 |
|---|---|---:|---:|---:|---:|---:|---:|
| CDE | xiDedit | BIN | M | D | S/P/D? | H | D |
| DCV | xiDimConvert | BIN | M | D | S/P/D? | H | D |
| DDT | xiDimDTogle | BIN | M | D | S/P/D? | H | D |
| DE | xiConDim | WRAP | M | D | S/P/D? | H | D |
| DG | xiDimGap | BIN | M | D | S/P/D? | H | D |
| DH | xiDimTextHome | BIN | M | D | S/P/D? | H | D |
| DLA | xiDimsExLineArrange | BIN | M | D | S/P/D? | H | D |
| DLL | xiDimsExLineLength | BIN | M | D | S/P/D? | H | D |
| DPL | xiDimPL | BIN | M | D | S/P/D? | H | D |
| DQ | xiQuickDim | BIN | M | D | S/P/D? | H | D |
| DSC | xiDimScale | BIN | M | D | S/P/D? | H | D |
| DSE | xiDimStyleEdit | BIN | M | D | S/P/D? | H | D |
| DSM | xiDimStyleMerge | BIN | M | D | S/P/D? | H | D |
| DTD | xiDimTxOverRideSep | CONTRACT | M | D | H | H | A |
| DTM | xiDimTextMove | BIN | M | D | S/P/D? | H | D |
| DTO | xiDimTxOverRide | BIN | M | D | S/P/D? | H | D |
| DU | xiDimUpdate | BIN | M | D | S/P/D? | H | D |
| DVD | xiDivideDim | CONTRACT | M | D | H | H | A |
| ED | xiEditDimScale | BIN | M | D | S/P/D? | H | D |
| IL | xiIntLen | BIN | M | D | S/P/D? | H | D |
| JD | xiJDims | CONTRACT | M | D | H | H | A |
| LDA | xiLeaderAlign | BIN | M | D | S/P/D? | H | D |
| LSE | xiLeaderStyleEdit | BIN | M | D | S/P/D? | H | D |
| LX | xiAutoLeader | BIN | M | D | S/P/D? | H | D |
| SD | xiSplitDim | BIN | M | D | S/P/D? | H | D |
| TL | xiText2Leader | BIN | M | D | S/P/D? | H | D |

### Shape (32)

| 별칭 | 함수 | 상태 | 유형 | COM | 입력 | 위험 | 배치 |
|---|---|---:|---:|---:|---:|---:|---:|
| 2DP | xi2dPro | BIN | M | G | S/P? | H | E |
| 3TP | xi3dPolyToLwPoly | RENAME | M | G | S/P? | H | E |
| BOO | xiBoo | BIN | M | G | S/P? | H | E |
| BS | xiBrkSymDCL | BIN | M | G | S/P? | H | E |
| CBJ | xiContourBoxJoin | BIN | M | G | S/P? | H | E |
| CM | xiCM | BIN | M | G | S/P? | H | E |
| CMW | xiCloudMarkWidth | BIN | M | G | S/P? | H | E |
| CP | xiCP | LIVE | M | G | H | H | 0 |
| DRL | xiDirectionLine | BIN | M | G | S/P? | H | E |
| JUL | xiJumpD | BIN | M | G | S/P? | H | E |
| K | xiK | BIN | M | G | S/P? | H | E |
| LEX | xiLTEx | BIN | M | G | S/P? | H | E |
| LXP | xiLineXp | BIN | M | G | S/P? | H | E |
| MTLT | xiMakeLt | BIN | M | G | S/P? | H | E |
| PBB | xiPBoundingBox | BIN | M | G | S/P? | H | E |
| PC | xiPolyClose | BIN | M | G | S/P? | H | E |
| PEC | xiPerCurve | BIN | M | G | S/P? | H | E |
| PJ | xiPolylineJoin | BIN | M | G | S/P? | H | E |
| PV | xiPlineVertexAdd | BIN | M | G | S/P? | H | E |
| PVL | xiPlineVertListTable | BIN | RO | G | S/P? | H | E |
| PVR | xiPlineVertexRemove | BIN | M | G | S/P? | H | E |
| PVV | xiPlineVertexV | BIN | M | G | S/P? | H | E |
| PW | xiPW | BIN | M | G | S/P? | H | E |
| PWD | xiPlineWidth | BIN | M | G | S/P? | H | E |
| R3 | xiR3P | BIN | M | G | S/P? | H | E |
| RND | xiRound | BIN | M | G | S/P? | H | E |
| RS | xiSolidBox | BIN | M | G | S/P? | H | E |
| UFD | xiUnfoldPoly | BIN | M | G | S/P? | H | E |
| V | xiV | BIN | M | G | S/P? | H | E |
| WE | xiPolyEndTab | WRAP | M | G | S/P? | H | E |
| XX | xiX | WRAP | M | G | S/P? | H | E |
| XZ | xiXZ | BIN | M | G | S/P? | H | E |

### Block (31)

| 별칭 | 함수 | 상태 | 유형 | COM | 입력 | 위험 | 배치 |
|---|---|---:|---:|---:|---:|---:|---:|
| ABX | xiAllBlockExplode | BIN | M | B | S/F/D? | C | F |
| B2X | xiBlock2Xref | BIN | M | B | S/F/D? | H | F |
| BAD | xiADDB | BIN | M | B | S/F/D? | H | F |
| BAM | xiBlockAutoMake | BIN | M | B | S/F/D? | H | F |
| BAR | xiABLRo | CONTRACT | M | B | H | H | A |
| BBL | xiLineBetweenBlock | BIN | M | B | S/F/D? | H | F |
| BCC | xiBlockConditionChange | BIN | M | B | S/F/D? | H | F |
| BCH | xiChgBlock | BIN | M | B | S/F/D? | H | F |
| BCO | xiBlkCopyDefinition | BIN | M | B | S/F/D? | H | F |
| BEX | xiExportBlock | BIN | IO | IO | S/F/D? | H | F |
| BIN | xiBchin | BIN | M | B | S/F/D? | H | F |
| BLA | xiBLKLAY | BIN | M | B | S/F/D? | H | F |
| BLX | xiMakeBlock | BIN | M | B | S/F/D? | H | F |
| BQT | xiBlkQty | BIN | RO | B | S/F/D? | H | F |
| BRM | xiREMB | BIN | M | B | S/F/D? | H | F |
| BRN | xiRenameBL | BIN | M | B | S/F/D? | H | F |
| BSC | xiBlkScaChange | BIN | M | B | S/F/D? | H | F |
| CX | xiCopy2xRef | BIN | M | B | S/F/D? | H | F |
| EAR | xiExpAttRemainTxt | BIN | M | B | S/F/D? | H | F |
| LII | xLi | RENAME | M | B | S/F/D? | H | F |
| M2B | xiMultiBlockChange | BIN | M | B | S/F/D? | H | F |
| MFB | xiMultiFilesChBlk | BIN | IO | IO | S/F/D? | C | F |
| MFX | xiMultiFilesChXref | BIN | IO | IO | S/F/D? | C | F |
| MX | xiMultiXclip | BIN | M | B | S/F/D? | H | F |
| Q11 | xiBlockLibrary | WRAP | M | B | S/F/D? | H | F |
| QWB | xiWblockExport | BIN | IO | IO | S/F/D? | H | F |
| RBP | xiRemoveBindPrefix | BIN | M | B | S/F/D? | H | F |
| WSL | xiWinSymList | BIN | M | B | S/F/D? | H | F |
| XCX | xiXclipXplode | BIN | M | B | S/F/D? | H | F |
| XRC | xiXrefColor | BIN | M | B | S/F/D? | H | F |
| XRR | xiResetXRefLayers | BIN | M | B | S/F/D? | H | F |

### Paper (11)

| 별칭 | 함수 | 상태 | 유형 | COM | 입력 | 위험 | 배치 |
|---|---|---:|---:|---:|---:|---:|---:|
| P2M | xiPsp2Msp | BIN | M | P | S/L/D? | H | F |
| VA | xiVportAlign | BIN | M | P | S/L/D? | H | F |
| VGL | xiVportGuideLine | BIN | RO | P | S/L/D? | H | F |
| VL | xiVpLock | BIN | M | P | S/L/D? | H | F |
| VLL | xiVpLockAll | BIN | M | P | S/L/D? | H | F |
| VMO | xiVportMakeObject | BIN | M | P | S/L/D? | H | F |
| VPP | xiVPLayProperty | BIN | M | P | S/L/D? | H | F |
| VR | xiVportViewRotate | BIN | M | P | S/L/D? | H | F |
| VSD | xiLayoutToDwgs | BIN | M | P | S/L/D? | H | F |
| VU | xiVpUnlock | BIN | M | P | S/L/D? | H | F |
| VUU | xiVpUnlockAll | BIN | M | P | S/L/D? | H | F |

### Plot (15)

| 별칭 | 함수 | 상태 | 유형 | COM | 입력 | 위험 | 배치 |
|---|---|---:|---:|---:|---:|---:|---:|
| ABD | xiAllNullBlockDelete | CONTRACT | M | M | H | C | A |
| AGD | xiAllGhostDelete | CONTRACT | M | M | H | C | A |
| APD | xiAllPointDelete | CONTRACT | M | M | H | C | A |
| BAK | xiDwgBackUp | BIN | IO | IO | F/S/D? | H | H |
| CER | xiCorrectError | BIN | M | M | F/S/D? | H | H |
| IB | xiInsertBlks | BIN | M | M | F/S/D? | H | H |
| LPD | xiLayerFiltersDelete | CONTRACT | M | M | H | C | A |
| LPU | xiDGNLineTypePurge | CONTRACT | M | M | H | C | A |
| MSL | xiMSlide | BIN | IO | IO | F/S/D? | H | H |
| PB | xiPlotBox | BIN | M | M | F/S/D? | H | H |
| PBD | xiDelPlotBox | BIN | M | M | F/S/D? | C | H |
| PBM | xiPlotBoxMultiMake | BIN | M | M | F/S/D? | H | H |
| PPP | xiAutoPlot | BIN | IO | IO | F/S/D? | H | H |
| PUA | xiPurgeAll | BIN | M | M | F/S/D? | C | H |
| SVS | xiSaveSep | BIN | IO | IO | F/S/D? | C | H |

### None (26)

| 별칭 | 함수 | 상태 | 유형 | COM | 입력 | 위험 | 배치 |
|---|---|---:|---:|---:|---:|---:|---:|
| % | xiPercent | CF | CF | C | N | L | 0 |
| * | xiMultiplication | CONTRACT | CF→M | C | N | L | A |
| - | xiSubtraction | CF | CF | C | N | L | 0 |
| / | xiDivision | CF | CF | C | N | L | 0 |
| = | xiAddition | CF | CF | C | N | L | 0 |
| A0 | xiSNGP | BIN | M | G | P/S? | M | I |
| A1 | xiSSNG | BIN | M | G | P/S? | M | I |
| CV | xiCopyValue | BIN | M | G | P/S? | M | I |
| ELM | xiELMark | BIN | M | G | P/S? | M | I |
| HT | xiHatchThickness | BIN | M | H | P/S? | M | I |
| KCI | xiKICI | BIN | M | G | P/S? | M | I |
| KCL | xiKICL | BIN | M | G | P/S? | M | I |
| MK | xiMask | WRAP | M | G | P/S? | M | I |
| MTB1 | xiMakeToiletBooth1 | CONTRACT | M | G | H | M | A |
| MTB2 | xiMakeToiletBooth2 | CONTRACT | M | G | H | M | A |
| PLM | xiPLMark | BIN | M | G | P/S? | M | I |
| PPB | xiPPB | BIN | M | G | P/S? | M | I |
| RD | xiRoofDrain | BIN | M | G | P/S? | M | I |
| RUB | xiRUB | BIN | M | G | P/S? | M | I |
| SAB | xiSaveAsBlock | BIN | IO | IO | P/S? | C | H |
| SCC | xiSC | CONTRACT | M | G | H | M | A |
| SCD | xiSCD | CONTRACT | M | G | H | M | A |
| SLD | xiScaleListDelete | EXCL | X | G | P/S? | C | X |
| SSL | xiSSL | BIN | M | G | P/S? | M | I |
| TBM | xiTBstyleMK | CONTRACT | M | T | H | M | A |
| WU | xiWU | BIN | M | G | P/S? | M | I |

## 집계와 권장 순서

| 배치 | 개수 | 목표 |
|---|---:|---|
| 0 | 36 | 현재 LIVE 또는 CAD-free |
| A | 16 | 기존 계약을 COM 어댑터로 연결 |
| B | 29 | 문자 |
| C | 28 | 레이어 |
| D | 23 | 치수 |
| E | 74 | 절단·변환·형상 편집 |
| F | 52 | 블록·도곽·뷰포트 |
| G | 44 | 도면 생성·해치 |
| H | 18 | 문서·외부 I/O·정리 |
| I | 36 | 기타 역분석 |
| X | 1 | 플랫폼 제외 |

### 높은 수율의 다음 작업

1. **A — 계약 보유, 어댑터 미연결**: 이미 Pydantic 계획이 있는 명령부터 COM postcondition과 Undo 검증을 붙인다.
2. **B/C — 문자·레이어**: `TextString/Height/StyleName`, `Layers.Item/entity.Layer/LayerOn/Freeze/Lock` 중심 공통 어댑터를 재사용한다.
3. **D — 치수**: `TextOverride`, 치수 스타일, extension line 속성을 fixture별로 분리하고 ZWCAD COM 차이를 확인한다.
4. **E — 기하 편집**: handle 선택, fingerprint, Undo mark, 생성/삭제 handle postcondition을 공통화한다.
5. **F/G**: 블록·XRef·뷰포트와 건축 생성 명령은 참조 DWG/스타일/동적 블록 자산 의존성을 계약화한다.
6. **H**: 저장·종료·plot·purge·외부 파일 변경은 별도 승인 토큰과 샌드박스 경로 제한 후 마지막에 승격한다.

## 명령별 완료 기준

각 행이 `LIVE` 또는 `CF`로 승격되려면 (1) 대화상자 없는 구조화 입력, (2) 사전 상태 fingerprint, (3) Drawing1에서 실제 COM 변경 또는 순수 계산, (4) postcondition, (5) Undo 복원(읽기/계산 제외), (6) ZWCAD 2025·2026 smoke 증거가 모두 필요하다. 레거시 엔트리포인트 357/357 로드는 이 기준을 충족하지 않는다.
