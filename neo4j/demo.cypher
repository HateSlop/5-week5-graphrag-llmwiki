// D1–D3를 사람이 확인해 입력한 교육용 관계. 전체 DB 삭제 명령은 없다.
MERGE (p:SessionDemo:Person {demo_key: 'person:ohesl'}) SET p.name = '오헤슬'
MERGE (j:SessionDemo:Project {demo_key: 'project:payment-refactor'}) SET j.name = '결제 시스템 리팩터링'
MERGE (g:SessionDemo:Program {demo_key: 'program:payment-stability'}) SET g.name = '결제 안정화 프로그램'
MERGE (t:SessionDemo:Team {demo_key: 'team:security'}) SET t.name = '보안팀'
MERGE (p)-[r1:LEADS {source_id: 'D1'}]->(j)
SET r1.evidence = '오헤슬은 결제 시스템 리팩터링 프로젝트를 총괄한다.', r1.demo = true
MERGE (j)-[r2:PART_OF {source_id: 'D2'}]->(g)
SET r2.evidence = '결제 시스템 리팩터링 프로젝트는 결제 안정화 프로그램에 속한다.', r2.demo = true
MERGE (t)-[r3:REVIEWS {source_id: 'D3'}]->(g)
SET r3.evidence = '보안팀은 결제 안정화 프로그램의 보안 검토를 담당한다.', r3.demo = true;

// Neo4j Browser에서 관계를 펼쳐 보기
MATCH (p:SessionDemo:Person {demo_key: 'person:ohesl'})-[r1:LEADS]->(j:SessionDemo:Project)-[r2:PART_OF]->(g:SessionDemo:Program)<-[r3:REVIEWS]-(t:SessionDemo:Team {demo_key: 'team:security'})
RETURN p, r1, j, r2, g, r3, t;

// 답변에 사용할 관계 종류, 방향, 출처 ID와 원문 근거
MATCH (p:SessionDemo:Person {demo_key: 'person:ohesl'})-[r1:LEADS]->(j:SessionDemo:Project)-[r2:PART_OF]->(g:SessionDemo:Program)<-[r3:REVIEWS]-(t:SessionDemo:Team {demo_key: 'team:security'})
RETURN p.name AS person, type(r1) AS relation1, r1.source_id AS source1, r1.evidence AS evidence1,
       j.name AS project, type(r2) AS relation2, r2.source_id AS source2, r2.evidence AS evidence2,
       g.name AS program, type(r3) AS relation3, r3.source_id AS source3, r3.evidence AS evidence3,
       t.name AS team;

