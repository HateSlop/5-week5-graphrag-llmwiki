# 데모 설계와 정확성 기준

## 1. 같은 자료에서 비교하는 것

벡터 RAG와 작은 관계 그래프에는 D1–D3의 동일한 문장을 사용합니다. Chroma 예제는 실제 회수 ID·순위를 보여주고, top-k=2라면 세 필요 근거 중 하나 이상이 빠진다는 **정보 범위**를 확인합니다. 그래프 예제는 세 문장을 사람이 검증해 `LEADS`, `PART_OF`, `REVIEWS`로 표현하고, 질문에 맞는 경로를 회수합니다. 두 예제는 같은 원문을 쓰지만 **자동화 수준이 다릅니다**. 이는 제품 성능 벤치마크가 아닙니다.

정책 A·B·C는 청킹·검색 범위의 문제를 보여줍니다. 그래프 없이도 부모 문서·이웃 청크·문맥 보강으로 개선할 수 있습니다. [Microsoft GraphRAG 기본 흐름](https://microsoft.github.io/graphrag/index/default_dataflow/)도 텍스트를 TextUnit으로 나눈 후 그래프를 추출합니다.

## 2. 왜 작은 그래프와 Microsoft GraphRAG를 따로 두나

작은 그래프는 관계 종류, 방향, 출처를 사람이 읽기 좋습니다. 그 과정은 `graph_facts.json`에 기록된 수동 추출입니다. Microsoft GraphRAG는 LLM 기반 엔터티·관계 추출, 커뮤니티 탐지·보고서, 임베딩과 Local/Global 검색을 포함하는 별도 파이프라인입니다. 기본 산출물은 Parquet 및 벡터 저장소이고 Neo4j가 필수는 아닙니다. [공식 Dataflow](https://microsoft.github.io/graphrag/index/default_dataflow/), [Outputs](https://microsoft.github.io/graphrag/index/outputs/)

Microsoft 출력의 관계에는 `text_unit_ids`가 있고, TextUnit에는 원문 텍스트와 `document_id`가 있습니다. 노트북은 이 연결을 따라가서 그래프의 관계가 어느 문장에 근거하는지 확인하게 합니다. [공식 Outputs](https://microsoft.github.io/graphrag/index/outputs/)

공식 PyPI의 3.2.0 설명은 이 프로젝트가 주로 유지보수 단계이며 연구·시연 성격이라고 밝힙니다. 따라서 이 세션에서는 **설계 패턴과 중간 산출물을 학습**하고, 서비스 도입 결론은 데이터·비용·품질을 별도로 평가하는 문제로 둡니다. [PyPI GraphRAG 3.2.0](https://pypi.org/project/graphrag/)

## 3. PDF 경로의 한계

공식 설정은 `input.type: markitdown`을 허용하고 여러 문서를 텍스트로 변환합니다. PDF에서 표·열 순서·그림·스캔 글자가 잘못 추출되면 그 뒤의 관계도 잘못될 수 있습니다. 이 저장소의 PDF 스크립트는 텍스트형 PDF를 생성하고 추출 가능 여부를 검사합니다. 외부 PDF나 스캔본의 성공을 보장하지 않습니다. [공식 입력 문서](https://microsoft.github.io/graphrag/index/inputs/), [설정 문서](https://microsoft.github.io/graphrag/config/yaml/)

## 4. LLM Wiki에서 구현과 원문 구분

[Karpathy의 원문](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)은 제품 명세가 아니라 작업 패턴 제안입니다. 원자료(raw), 에이전트가 유지하는 Markdown 위키(wiki), 운영 규칙(schema)의 세 층과 ingest/query/lint 작업을 설명합니다. Obsidian과 qmd는 선택 도구입니다. 이 프로젝트의 디렉터리명·CLI·JSON 계획은 **세션용 구체화**입니다.

- `fixture` ingest: 사람이 미리 작성한 D6 변경안을 적용해 전후 diff를 안정적으로 재현합니다.
- `llm` ingest: 모델이 현재 위키와 D6를 읽고 여러 페이지의 완전한 새 내용을 제안합니다. 경로·출처·현재/과거 날짜를 코드가 검사한 뒤 plan 파일로 저장합니다. 사람이 diff를 보고 같은 plan을 적용합니다.
- `extractive` query: 검색된 페이지와 날짜·이유를 규칙으로 표시하는 오프라인 리허설입니다.
- `llm` query: 인덱스·관련 위키·인용된 raw를 모델에 제공해 근거가 붙은 답변을 요청합니다.
- 기본 lint: 링크·출처·현재 날짜 충돌 등 검사 가능한 항목. `--llm` lint: 의미상 모순과 조사 공백에 대한 모델 제안.

위키 링크 그래프는 페이지 사이의 **연결**입니다. Neo4j 예제의 관계는 출처가 붙은 **사실 문장**입니다. LLM Wiki의 query에는 검색이 들어갈 수 있으며, RAG와의 차이는 지속해서 갱신하는 지식 페이지를 주요 산출물로 둔다는 데 있습니다.

## 5. 이번 자료에서 입증하지 않는 것

- GraphRAG가 모든 RAG보다 정확하다는 주장
- 작은 여섯 문서에서 Microsoft Global Search가 우수하다는 주장
- 임의 PDF를 넣으면 올바른 그래프가 항상 자동 생성된다는 주장
- 그래프 경로가 있다는 이유로 오헤슬과 보안팀이 직접 협업했다는 주장
- fixture diff가 실시간 에이전트의 산출물이라는 주장

