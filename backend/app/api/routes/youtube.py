from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import AppState, get_app_state

router = APIRouter(prefix="/youtube", tags=["youtube"])


@router.get("/status")
async def status(state: AppState = Depends(get_app_state)):
    """Reports configuration honestly; the UI renders a setup notice, never a
    fabricated video list, when the API key is absent."""
    return await state.discovery.status()


@router.get("/discover")
async def discover(
    q: str = Query(default="", max_length=200),
    max_results: int = Query(default=12, ge=1, le=25),
    department: str | None = Query(default=None, max_length=16),
    subject: str | None = Query(default=None, max_length=24),
    topic_name: str | None = Query(default=None, max_length=140),
    subject_name: str | None = Query(default=None, max_length=140),
    state: AppState = Depends(get_app_state),
):
    return await state.discovery.discover(
        q,
        max_results=max_results,
        department_code=department,
        subject_code=subject,
        topic_name=topic_name,
        subject_name=subject_name,
    )


@router.get("/topics/{topic_code}")
async def discover_for_topic(
    topic_code: str,
    max_results: int = Query(default=12, ge=1, le=25),
    state: AppState = Depends(get_app_state),
):
    """Video discovery anchored to a real taxonomy topic, so the results land in
    the right department/subject context."""
    topic = await state.taxonomy.get_topic(topic_code)
    subject = await state.taxonomy.get_subject(topic.subject_code)
    return await state.discovery.discover_for_topic(
        topic.name,
        subject_name=subject.name,
        department_code=subject.department_code,
        subject_code=subject.code,
        max_results=max_results,
    )


@router.get("/subjects/{subject_code}")
async def discover_for_subject(
    subject_code: str,
    max_results: int = Query(default=12, ge=1, le=25),
    state: AppState = Depends(get_app_state),
):
    subject = await state.taxonomy.get_subject(subject_code)
    return await state.discovery.discover(
        subject.name,
        max_results=max_results,
        department_code=subject.department_code,
        subject_code=subject.code,
        subject_name=subject.name,
    )
