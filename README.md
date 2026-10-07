# GraphRAG & LLM Wiki 실습 자료

GraphRAG와 LLM Wiki를 같은 가상 자료로 살펴보는 실습 자료입니다. 모든 인물·팀·프로젝트·일정은 가상입니다.

## 학습 내용

| 순서 | 자료 | 주요 내용 |
| --- | --- | --- |
| 1 | `01_vector_rag.ipynb` | 청크 A·B·C의 예외 누락, D1–D3에서 실제 Chroma 검색 순위와 top-k=2의 근거 부족 |
| 2 | `02_graph_neo4j.ipynb` | D1–D3에서 명시한 관계, 방향, 출처와 세 단계 경로. Neo4j가 없으면 동일한 그래프를 로컬에서 먼저 시각화 |
| 3 | `03_microsoft_graphrag.ipynb` | Microsoft GraphRAG의 TextUnit·엔터티·관계·커뮤니티 보고서 산출물 및 Local/Global 질의 |
| 4 | `04_llm_wiki.ipynb` | D6 전후 기존 위키 여러 페이지의 변경, `ingest`·`query`·`lint`와 Obsidian 링크 그래프 |

같은 D1–D6 가상 자료를 사용합니다. **첫 번째 비교는 검색된 근거의 차이를 보여주는 작은 실험**입니다. GraphRAG가 모든 질문에서 우수하다는 실험 결과로 해석하지 않습니다. 정책 예외(A·B·C)는 그래프만의 해결 문제가 아니므로 이웃 청크·부모 문서 회수도 함께 살펴봅니다.

## 폴더 지도

```text
graphrag_llmwiki/
├─ notebooks/                 순서대로 실행하는 네 개의 노트북
├─ session_demo/              노트북과 CLI가 함께 쓰는 Python 코드
├─ data/
│  ├─ project/                D1–D6 원자료
│  ├─ policy_chunks.json      정책 예외 A–C
│  └─ graph_facts.json        D1–D3에서 확인한 수업용 구조화 결과
├─ wiki_vault/                D1–D5가 반영된 Obsidian 호환 초기 위키
├─ fixtures/wiki_plan_D6.json API 없이 재현하는 D6 변경 계획
├─ scripts/                   PDF·Microsoft 작업공간 준비, 노트북 생성
├─ docs/                      실습 흐름과 설계·출처 설명
├─ environment.yml            Conda Python 3.12 환경
├─ requirements.txt           기본 데모 의존성
└─ requirements-microsoft.txt Microsoft GraphRAG 3.2.0 추가 의존성
```

## 설치

PowerShell에서 이 폴더로 이동한 뒤 실행합니다. 환경 이름은 `hateslop-graphrag-wiki`입니다.

```powershell
conda env create -f environment.yml
conda activate hateslop-graphrag-wiki
python -m pip install -r requirements.txt
python -m ipykernel install --user --name hateslop-graphrag-wiki --display-name "Python (GraphRAG LLM Wiki)"
```

Microsoft GraphRAG 인덱싱까지 실행하려면 추가 설치합니다.

```powershell
python -m pip install -r requirements-microsoft.txt
```

`conda env create` 전에 같은 이름의 환경이 이미 있다면 `conda env update -f environment.yml`을 사용합니다. 저장소에 API 키를 넣지 않습니다. 프로젝트 루트에서 `.env.example`을 `.env`로 복사하고 `OPENAI_API_KEY`를 한 번만 채웁니다. Microsoft GraphRAG의 `runs/microsoft/.env`는 초기화 명령이 자동 생성한 빈 템플릿이므로 준비 스크립트가 제거합니다. 노트북과 `scripts/microsoft_cli.py`는 루트 `.env`를 읽습니다. 01·03·04의 선택 API 호출이 이 값을 사용합니다. Chroma 검색·로컬 그래프·준비된 위키 변경 계획·규칙 기반 lint는 API 키 없이 실행됩니다. **Microsoft GraphRAG 인덱싱과 실제 LLM 위키 갱신/답변에는 유료 모델 API 호출이 필요합니다.**

## 노트북 실행

VS Code에서 `notebooks/01_vector_rag.ipynb`부터 `04_llm_wiki.ipynb`까지 순서대로 열고, 커널 `Python (GraphRAG LLM Wiki)`을 선택해 실행합니다. `02`의 Neo4j 연결, `03`의 실제 인덱싱·질의, `04`의 LLM 호출은 선택 사항입니다. `03`의 실제 인덱싱에는 위의 Microsoft 추가 의존성과 API 키가 필요합니다.

### CLI로 위키 흐름 확인하기 (선택)

1. `python -m session_demo.wiki_cli prepare --destination runs/wiki_demo`로 D1–D5 상태의 위키를 복사합니다.
2. `python -m session_demo.wiki_cli ingest --vault runs/wiki_demo --source data/project/D6_decision.md --mode fixture --plan runs/D6_plan.json`으로 **미리 작성된 예시 변경안**과 diff를 봅니다.
3. `python -m session_demo.wiki_cli apply --vault runs/wiki_demo --plan runs/D6_plan.json`으로 검토한 변경안을 반영합니다.
4. `python -m session_demo.wiki_cli query --vault runs/wiki_demo --question "현재 출시 목표일은 언제이며 왜 바뀌었나?" --mode extractive`와 `python -m session_demo.wiki_cli lint --vault runs/wiki_demo`를 실행합니다.
5. Obsidian에서 `runs/wiki_demo`를 vault로 열어 링크 그래프와 변경된 페이지를 보여줍니다.

`fixture`는 미리 작성한 변경안을 로드하며 실제 에이전트가 생성한 결과는 아닙니다. `--mode llm`으로 새 계획을 만들었다면 **같은 plan 파일을 검토한 뒤** `apply`합니다. `04_llm_wiki.ipynb`는 두 경로를 나란히 안내합니다. 실제 LLM 계획은 출처·날짜·영향 페이지 검증에 실패할 수 있으며, 그 경우 후보 JSON만 남기고 적용하지 않습니다. query와 의미 lint는 계획의 성공 여부와 별도로 볼 수 있습니다. 의미 lint의 제안도 기계적 lint와 원문으로 대조합니다.

## Neo4j를 사용하는 경우

Neo4j Desktop 또는 로컬 Neo4j 인스턴스를 실행하고 `.env`에 `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`를 설정합니다. Neo4j를 사용하려면 `02_graph_neo4j.ipynb`의 마지막 셀에서 `CONNECT_NEO4J=True`로 바꿉니다. 이 셀은 `SessionDemo` 라벨을 가진 노드와 D1–D3 관계만 `MERGE`합니다. 기존 데이터베이스를 전체 삭제하는 명령은 없습니다. Browser에서 노드를 펼쳐 보고, 노트북에 있는 Cypher로 관계 방향·출처·원문 문장을 확인합니다.

## Microsoft GraphRAG를 사용하는 경우

```powershell
python scripts/prepare_microsoft.py --format text
# 프로젝트 루트 .env에 OPENAI_API_KEY를 한 번만 설정
python scripts/microsoft_cli.py index --root runs/microsoft --method standard --dry-run --skip-validation
python scripts/microsoft_cli.py index --root runs/microsoft --method standard
python scripts/microsoft_cli.py query "오헤슬과 보안팀은 어떤 관계인가?" --root runs/microsoft --method local
```

`prepare_microsoft.py --format pdf`는 D1–D6를 각각 PDF로 만들어 MarkItDown 입력을 설정합니다. 프로젝트·프로그램·팀·사람을 추출 대상 유형으로 추가합니다. **PDF의 텍스트 추출 결과를 먼저 확인**한 후 인덱싱합니다. 작은 여섯 문서는 파이프라인의 중간 산출물을 살펴보기 위한 예시입니다. 커뮤니티 분석의 성능을 입증하는 데이터셋이 아닙니다. `03_microsoft_graphrag.ipynb`에서는 Parquet 산출물과 출처 ID를 읽고 Local/Global 질의를 선택적으로 실행합니다. 질의 결과는 노트북에 표시하고 `runs/microsoft/query_local_answer.md`·`query_global_answer.md`에도 저장합니다. 질의를 다시 실행하지 않아도 저장된 답변을 다음 셀에서 열 수 있습니다. 원문 경로 감사 셀은 D1→D2←D3 연결의 출처를 보여줍니다. Local·Global 생성 답변은 원문 경로와 출처를 대조해 확인합니다.

`--dry-run --skip-validation`은 파이프라인 설정을 확인하되 모델 연결 확인은 건너뜁니다. 실제 인덱싱에는 유효한 API 키가 필요합니다. GraphRAG가 처음 사용할 때 `tiktoken` 인코딩 데이터를 내려받아야 할 수도 있습니다.

## 구현 구분

- `graph_facts.json`과 Neo4j 작은 그래프는 D1–D3에서 **사람이 확인해 입력한 교육용 그래프**입니다. 자동 관계 추출로 소개하지 않습니다.
- Microsoft GraphRAG는 자체 인덱싱·질의 파이프라인입니다. Neo4j 설치가 필수는 아닙니다. 기본 산출물은 Parquet 표와 벡터 저장소에 저장됩니다.
- Chroma 예제는 한국어 문자 n-gram TF-IDF 벡터를 직접 전달합니다. 인터넷에서 모델을 내려받지 않고 검색 절차를 재현하기 위한 선택이며, 최신 의미 임베딩의 품질을 대표하지 않습니다.
- LLM Wiki의 핵심은 유지되는 Markdown 지식 페이지입니다. Obsidian은 파일과 페이지 링크를 읽고 보여주는 화면입니다.

구현 방식과 출처는 [설계 노트](docs/DESIGN.md)에 정리되어 있습니다.

## 주요 원문

- [Microsoft GraphRAG 시작하기](https://microsoft.github.io/graphrag/get_started/), [인덱싱 흐름](https://microsoft.github.io/graphrag/index/default_dataflow/), [출력 스키마](https://microsoft.github.io/graphrag/index/outputs/), [질의 방법](https://microsoft.github.io/graphrag/query/overview/)
- [Andrej Karpathy, LLM Wiki 원문](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)
- [Neo4j Python Driver 매뉴얼](https://neo4j.com/docs/python-manual/current/)
