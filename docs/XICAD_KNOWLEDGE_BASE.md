# XiCAD Deep Knowledge Base
This document contains a highly detailed breakdown of the internal structure and domain rules extracted from `C:/xicad`.
It is intended to provide HS-CAD agents with full visibility into the assets and rules available.

## 1. Global Statistics
- **total_files**: 2418
- **ext_.slb**: 29
- **ext_.shx**: 17
- **ext_.dvb**: 1
- **ext_.xml**: 2
- **ext_.dll**: 29
- **ext_.banner**: 1
- **ext_.arx**: 19
- **ext_.zrx**: 5
- **ext_.chm**: 3
- **ext_.txt**: 10
- **ext_.dfs**: 2
- **ext_.bmp**: 81
- **ext_.exe**: 3
- **ext_.ini**: 1
- **ext_.lsp**: 11
- **ext_.dcl**: 80
- **ext_.dwg**: 1700
- **ext_.bak**: 12
- **ext_.des**: 28
- **ext_.fas**: 28
- **ext_.zelx**: 28
- **ext_.dat**: 6
- **ext_.vls**: 1
- **ext_.vlx**: 1
- **ext_.key**: 2
- **ext_.ctb**: 6
- **ext_.stb**: 1
- **ext_.lay**: 2
- **ext_.lcd**: 1
- **ext_.cfg**: 3
- **ext_.zae**: 1
- **ext_.dwl**: 2
- **ext_.dwl2**: 2
- **ext_.sld**: 237
- **ext_.pat**: 13
- **ext_.dwt**: 12
- **ext_.lin**: 10
- **ext_.mln**: 4
- **ext_.pgp**: 7
- **ext_.cuix**: 6
- **ext_.cui**: 2
- **ext_.mnr**: 4
- **ext_.mns**: 2
- **ext_.menuc**: 1
- **ext_.menur**: 1
- **ext_.fmp**: 1
- **.des**: 28
- **.fas**: 28
- **.zelx**: 28
- **.slb**: 2
- **.dat**: 6
- **.vls**: 1
- **.vlx**: 1
- **.dcl**: 4
- **.key**: 1
- **.lsp**: 1

## 2. Text Presets & Leaders
### Auto Leaders
- `필로티(상부)`
- `도기질타일`
- `도기칠 타일`
- `건축한계선`
- `간선도로`
- `곰보빵`
- `곰보빵fkdsal`
- `우리는`
- `지시선 문자11`
- `하하하`
### Common Texts
- `*****Group01*****분류1: 제목`
- `기존 보 하단 선`
- `fdgdfsgfds`
- `대지 내,외부 도로 선형`
- `앵글, C, L 등 형강 표현`
- `철물`
- `천장마감재, 달대 등`
- `작은 DIM`
- `입면도에서의 장식적 표현`
- `앵글, C, L 등 형강 표현`
- `철물`
- `천장마감재, 달대 등`
- `작은 DIM`
- `입면도에서의 장식적 표현`
- `*****Group02*****분류2`
- `천장마감재, 달대 등`
- `작은 DIM`
- `입면도에서의 장식적 표현`
- `앵글, C, L 등 형강 표현`
- `철물`
- `천장마감재, 달대 등`
- `*****Group03*****분류3: 제목 및 설명`
- `ttttttthgf`
- `앵글, C, L 등 형강 표현`
- `철물`
- `천장마감재, 달대 등`
- `작은 DIM`
- `입면도에서의 장식적 표현`
- `*****Group04*****분류4: 제목 및 설명`
- `ttttt`
- `앵글, C, L 등 형강 표현`
- `철물`
- `천장마감재, 달대 등`
- `작은 DIM`
- `입면도에서의 장식적 표현`
- `*****Group05*****분류5: 제목 및 설명`
- `*****Group06*****분류6: 제목 및 설명`
- `*****Group07*****분류7: 제목 및 설명`
- `*****Group08*****분류8: 제목 및 설명`
- `*****Group09*****분류9: 제목 및 설명`
- `*****Group10*****분류10: 제목 및 설명`
- `*****Group11*****분류11: 제목 및 설명`
- `*****Group12*****분류12: 제목 및 설명`
### Text Boxes
- `현관`
- `계단실`
- `드레스룸`
- `안방`
- `주방`
- `거실`
- `화장실`
- `거   실`
- `화 장 실`
- `제2종 근린생활시설`
- `AB`
- `A`
- `A B C`

## 3. Configuration & System Files
### `SpecialChar.ini`
```ini
[Position]
Top=300
Left=488
... (truncated)
```

## 4. Slide Libraries (.slb)
Contains thumbnail UI catalogs for ZWCAD/AutoCAD dialogs.
- `acad.slb` (429.7 KB)
- `acad12.slb` (96.2 KB)
- `han.slb` (85.8 KB)
- `kxi.slb` (227.2 KB)
- `ldoor.slb` (65.6 KB)
- `lelev.slb` (30.6 KB)
- `lfurn.slb` (106.1 KB)
- `lkitc.slb` (88.9 KB)
- `lland.slb` (49.9 KB)
- `ltoil.slb` (199.8 KB)
- `lwind.slb` (263.7 KB)
- `mcd.slb` (5.7 KB)
- `struct.slb` (140.5 KB)
- `xi1.slb` (143.4 KB)
- `xi2.slb` (67.8 KB)
- `xi3d.slb` (67.8 KB)
- `xi95.slb` (8.5 KB)
- `xilib3d.slb` (194.9 KB)
- `xiMark.slb` (0.4 KB)
- `xiToilet.slb` (16.9 KB)
- `xiUtil.slb` (141.4 KB)
- `xi_fur3.slb` (287.3 KB)
- `xi_tr_3.slb` (489.0 KB)
- `xi_tr_e.slb` (428.0 KB)
- `xi_tr_p.slb` (553.9 KB)
- `Lisp\xiBeam.slb` (42.6 KB)
- `Lisp\xilib3d.slb` (194.9 KB)
- `_GstarCad\gcad.slb` (429.7 KB)
- `_ZWCad\zwcad.slb` (429.7 KB)

## 5. Lisp Assets
Total compiled components (.fas, .des, .zelx): ~84
Readable Lisp scripts:
- `_onekey.lsp`