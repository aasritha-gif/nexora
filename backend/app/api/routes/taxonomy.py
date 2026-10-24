from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import (
    AppState,
    get_app_state,
    require_role,
)
from app.models.taxonomy import Department, Subject, Topic
from app.models.user import Role, User
from app.schemas.search import SearchFilters
from app.schemas.taxonomy import (
    DepartmentDetailResponse,
    DepartmentResponse,
    DepartmentUpdateRequest,
    SubjectCreateRequest,
    SubjectResponse,
    TaxonomyBrowseResponse,
    TopicCreateRequest,
    TopicResponse,
)

router = APIRouter(tags=["taxonomy"])


@router.get("/browse", response_model=TaxonomyBrowseResponse)
async def browse(state: AppState = Depends(get_app_state)):
    """The Knowledge Universe: every department with its live counts."""
    departments = await state.taxonomy.list_departments()
    resource_counts = await state.resources.counts_by_department()
    names = await state.taxonomy.name_maps()
    topic_names = names["topic"]

    async def to_response(dept: Department) -> DepartmentResponse:
        subject_count = len(await state.taxonomy.list_subjects(dept.code))
        trending_codes = await state.resources.trending_topics(dept.code, limit=5)
        return DepartmentResponse(
            code=dept.code,
            name=dept.name,
            description=dept.description,
            icon=dept.icon,
            color=dept.color,
            resource_count=resource_counts.get(dept.code, 0),
            subject_count=subject_count,
            trending_topics=[topic_names.get(code, code) for code in trending_codes],
        )

    return TaxonomyBrowseResponse(
        departments=[await to_response(dept) for dept in departments]
    )


@router.get("/departments/{code}", response_model=DepartmentDetailResponse)
async def department_detail(
    code: str,
    state: AppState = Depends(get_app_state),
):
    dept = await state.taxonomy.get_department(code)
    subjects = await state.taxonomy.list_subjects(dept.code)
    subject_counts = await state.resources.counts_by_subject(dept.code)
    names = await state.taxonomy.name_maps()
    topic_names = names["topic"]

    topic_counts: dict[str, int] = {}
    for subject in subjects:
        topic_counts.update(await state.resources.counts_by_topic(subject.code))

    subject_responses = [
        SubjectResponse(
            code=subject.code,
            name=subject.name,
            department_code=subject.department_code,
            description=subject.description,
            semester=subject.semester,
            resource_count=subject_counts.get(subject.code, 0),
            topic_count=0,
        )
        for subject in subjects
    ]
    # Topics are grouped under their subject in one pass to keep the response
    # shaped the way the UI renders it.
    by_subject: dict[str, list[TopicResponse]] = {}
    for topic in await state.taxonomy.list_topics():
        by_subject.setdefault(topic.subject_code, []).append(
            TopicResponse(
                code=topic.code,
                name=topic.name,
                subject_code=topic.subject_code,
                description=topic.description,
                resource_count=topic_counts.get(topic.code, 0),
            )
        )
    for subject_response in subject_responses:
        topics = by_subject.get(subject_response.code, [])
        subject_response.topics = topics
        subject_response.topic_count = len(topics)

    popular = await state.resources.popular(limit=6, department=dept.code)
    recent = await state.resources.recent(limit=6, department=dept.code)
    trending_codes = await state.resources.trending_topics(dept.code, limit=8)

    return DepartmentDetailResponse(
        code=dept.code,
        name=dept.name,
        description=dept.description,
        icon=dept.icon,
        color=dept.color,
        resource_count=sum(subject_counts.values()),
        subject_count=len(subjects),
        trending_topics=[topic_names.get(c, c) for c in trending_codes],
        subjects=subject_responses,
        popular_resources=[r.model_dump(mode="json") for r in await state.resource_service.hydrate_many(popular)],
        new_resources=[r.model_dump(mode="json") for r in await state.resource_service.hydrate_many(recent)],
    )


@router.get("/subjects/{code}")
async def subject_detail(
    code: str,
    limit: int = Query(default=12, ge=1, le=48),
    state: AppState = Depends(get_app_state),
):
    subject = await state.taxonomy.get_subject(code)
    dept = await state.taxonomy.get_department(subject.department_code)
    topics = await state.taxonomy.list_topics(subject.code)
    topic_counts = await state.resources.counts_by_topic(subject.code)

    filters = SearchFilters(query="", subject=subject.code, types=[])
    resources, total = await state.resources.query(filters, limit=limit, sort=[("stats.views", -1)])
    hydrated = await state.resource_service.hydrate_many(resources)

    return {
        "subject": SubjectResponse(
            code=subject.code,
            name=subject.name,
            department_code=subject.department_code,
            description=subject.description,
            semester=subject.semester,
            resource_count=total,
            topic_count=len(topics),
        ).model_dump(mode="json"),
        "department": {"code": dept.code, "name": dept.name},
        "topics": [
            TopicResponse(
                code=topic.code,
                name=topic.name,
                subject_code=topic.subject_code,
                description=topic.description,
                resource_count=topic_counts.get(topic.code, 0),
            ).model_dump(mode="json")
            for topic in topics
        ],
        "resources": [r.model_dump(mode="json") for r in hydrated],
    }


@router.get("/topics/{code}")
async def topic_detail(
    code: str,
    limit: int = Query(default=12, ge=1, le=48),
    state: AppState = Depends(get_app_state),
):
    topic = await state.taxonomy.get_topic(code)
    subject = await state.taxonomy.get_subject(topic.subject_code)

    filters = SearchFilters(query="", topic=topic.code, types=[])
    resources, total = await state.resources.query(filters, limit=limit, sort=[("stats.views", -1)])
    hydrated = await state.resource_service.hydrate_many(resources)

    return {
        "topic": TopicResponse(
            code=topic.code,
            name=topic.name,
            subject_code=topic.subject_code,
            description=topic.description,
            resource_count=total,
        ).model_dump(mode="json"),
        "subject": {"code": subject.code, "name": subject.name},
        "department_code": subject.department_code,
        "resources": [r.model_dump(mode="json") for r in hydrated],
    }


@router.get("/graph")
async def knowledge_graph(state: AppState = Depends(get_app_state)):
    """Department → Subject → Topic structure as held in Neo4j.

    Reported as unavailable rather than reconstructed from MongoDB: this view
    exists to show what the graph database actually contains."""
    if not state.graph.available:
        return {
            "available": False,
            "reason": state.databases.neo4j.reason or "graph database not connected",
            "nodes": [],
            "edges": [],
        }
    rows = await state.graph.department_graph()
    nodes: list[dict] = []
    edges: list[dict] = []
    seen: set[tuple[str, str]] = set()

    for row in rows:
        dept_key = ("department", row["department"])
        if dept_key not in seen:
            seen.add(dept_key)
            nodes.append({
                "id": row["department"], "label": row["department_name"],
                "kind": "department",
            })
        subject_key = ("subject", row["subject"])
        if subject_key not in seen:
            seen.add(subject_key)
            nodes.append({
                "id": row["subject"], "label": row["subject_name"],
                "kind": "subject", "resource_count": row.get("resource_count", 0),
            })
            edges.append({"source": row["department"], "target": row["subject"],
                          "relation": "CONTAINS"})
        for topic_name in row.get("topics") or []:
            edges.append({"source": row["subject"], "target": topic_name,
                          "relation": "HAS_TOPIC"})

    return {"available": True, "reason": None, "nodes": nodes, "edges": edges}


@router.patch("/admin/departments/{code}", response_model=DepartmentResponse)
async def update_department(
    code: str,
    data: DepartmentUpdateRequest,
    admin: User = Depends(require_role(Role.ADMIN)),
    state: AppState = Depends(get_app_state),
):
    dept = await state.taxonomy.update_department(
        code, data.model_dump(exclude_unset=True, exclude_none=True)
    )
    await _sync_department(state, dept)
    return DepartmentResponse(
        code=dept.code, name=dept.name, description=dept.description,
        icon=dept.icon, color=dept.color,
        resource_count=await state.resources.count(department=dept.code),
        subject_count=len(await state.taxonomy.list_subjects(dept.code)),
    )


@router.post("/admin/subjects", response_model=SubjectResponse, status_code=201)
async def create_subject(
    data: SubjectCreateRequest,
    admin: User = Depends(require_role(Role.ADMIN)),
    state: AppState = Depends(get_app_state),
):
    subject = Subject(
        code=data.code,
        name=data.name,
        department_code=data.department_code.upper(),
        description=data.description,
        semester=data.semester,
    )
    await state.taxonomy.upsert_subject(subject)
    if state.graph.available:
        await state.graph.sync_subject(subject.code, subject.name, subject.department_code)
    return SubjectResponse(
        code=subject.code, name=subject.name,
        department_code=subject.department_code,
        description=subject.description, semester=subject.semester,
    )


@router.post("/admin/topics", response_model=TopicResponse, status_code=201)
async def create_topic(
    data: TopicCreateRequest,
    admin: User = Depends(require_role(Role.ADMIN)),
    state: AppState = Depends(get_app_state),
):
    topic = Topic(
        code=data.code, name=data.name, subject_code=data.subject_code,
        description=data.description,
    )
    await state.taxonomy.upsert_topic(topic)
    if state.graph.available:
        await state.graph.sync_topic(topic.code, topic.name, topic.subject_code)
    return TopicResponse(
        code=topic.code, name=topic.name, subject_code=topic.subject_code,
        description=topic.description,
    )


async def _sync_department(state: AppState, dept: Department) -> None:
    """Taxonomy edits propagate to the graph when the graph is reachable."""
    if not state.graph.available:
        return
    try:
        await state.graph.sync_department(dept.code, dept.name)
    except Exception:  # noqa: BLE001 - graph lag must not fail the admin edit
        pass
