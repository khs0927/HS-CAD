# 29. Operational Corpus Workflow

이 문서는 HS-CAD 도면 지식 코퍼스를 운영형으로 사용하는 절차를 설명한다.

## 목적

기존 단계에서 다음이 구현되었다.

1. 도면 파일화
2. fileized JSON ingest
3. 재료·규격·치수·상황·상세 패턴 추출
4. SQLite KnowledgeStore
5. corpus-next learn/query/report

이번 운영형 단계에서는 다음을 추가한다.

- 검색어 확장
- 증거 패키지 생성
- 상황/재료/규격 관계 그래프
- 코퍼스 품질 감사
- CompanyDraftingProfile 기반 출력 계획
- JSONL export

## 명령

```bash
python -m src.main corpus-ops audit --kb outputs/corpus_test/cad_knowledge.sqlite --out outputs/corpus_ops
python -m src.main corpus-ops graph --kb outputs/corpus_test/cad_knowledge.sqlite --out outputs/corpus_ops
python -m src.main corpus-ops query-pack --kb outputs/corpus_test/cad_knowledge.sqlite --query "판넬 두께와 H빔 접합" --out outputs/corpus_ops
python -m src.main corpus-ops export-jsonl --kb outputs/corpus_test/cad_knowledge.sqlite --out outputs/corpus_ops/dataset.jsonl
python -m src.main corpus-ops plan-output --evidence outputs/corpus_ops/evidence_pack.json --company-profile outputs/company_profile/company_drafting_profile.json --out outputs/corpus_ops
```

## 출력

- `corpus_audit.json/md`
- `relationship_graph.json/md`
- `evidence_pack.json/md`
- `dataset.jsonl`
- `company_output_plan.json/md`

## 원칙

외부 도면의 스타일은 가져오지 않는다.  
외부 도면의 건축 지식만 가져온다.  
최종 출력은 HS-CAD 내부 회사 기준과 현재 도면 주변 속성 샘플링을 따른다.
