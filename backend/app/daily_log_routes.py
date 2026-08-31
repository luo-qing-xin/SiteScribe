from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from .auth import current_user, get_db, require_member
from .daily_log_schemas import (
    DailyLogCreate,
    DailyLogListOut,
    DailyLogOut,
    DailyLogPatch,
    DailyLogVersionSummary,
)
from .daily_log_service import (
    confirm_daily_log,
    create_daily_log,
    daily_log_out,
    patch_daily_log,
    refresh_daily_log,
    version_summaries,
)
from .models import DailyLogDocument, DailyLogVersion, Project, User

router = APIRouter(prefix="/api", tags=["Daily Logs"])


def _project_for_user(db: Session, project_id: int, user: User) -> Project:
    require_member(db, user.id, project_id)
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    return project


def _version_for_user(db: Session, log_id: str, user: User) -> DailyLogVersion:
    version = db.get(DailyLogVersion, log_id)
    if not version:
        raise HTTPException(status_code=404, detail="日志版本不存在")
    require_member(db, user.id, version.project_id)
    return version


@router.get(
    "/projects/{project_id}/daily-logs",
    response_model=DailyLogListOut,
    summary="读取项目某日施工日志和安全日志",
)
def list_daily_logs(
    project_id: int,
    log_date: date = Query(alias="date"),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    _project_for_user(db, project_id, user)
    documents = (
        db.query(DailyLogDocument)
        .filter_by(project_id=project_id, log_date=log_date)
        .order_by(DailyLogDocument.log_type)
        .all()
    )
    logs: list[DailyLogOut] = []
    for document in documents:
        version = (
            db.query(DailyLogVersion)
            .filter_by(document_id=document.id)
            .order_by(DailyLogVersion.version.desc())
            .first()
        )
        if version:
            logs.append(daily_log_out(db, version))
    return DailyLogListOut(date=log_date, logs=logs)


@router.post(
    "/projects/{project_id}/daily-logs",
    response_model=DailyLogOut,
    status_code=201,
    summary="幂等创建默认日志草稿",
)
def create_project_daily_log(
    project_id: int,
    payload: DailyLogCreate,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    project = _project_for_user(db, project_id, user)
    version = create_daily_log(db, project, payload.date, payload.log_type, user.id)
    return daily_log_out(db, version)


@router.get(
    "/daily-logs/{log_id}",
    response_model=DailyLogOut,
    summary="读取指定日志版本",
)
def read_daily_log(log_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return daily_log_out(db, _version_for_user(db, log_id, user))


@router.patch(
    "/daily-logs/{log_id}",
    response_model=DailyLogOut,
    summary="保存日志人工补录与安全问题归类",
)
def update_daily_log(
    log_id: str,
    payload: DailyLogPatch,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    version = _version_for_user(db, log_id, user)
    patch_daily_log(db, version, payload.manual_content, user.id)
    return daily_log_out(db, version)


@router.post(
    "/daily-logs/{log_id}/refresh",
    response_model=DailyLogOut,
    summary="显式刷新日志来源；已确认日志产生新版本",
)
def refresh_log(log_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    version = _version_for_user(db, log_id, user)
    return daily_log_out(db, refresh_daily_log(db, version, user.id))


@router.post(
    "/daily-logs/{log_id}/confirm",
    response_model=DailyLogOut,
    summary="人工确认日志版本",
)
def confirm_log(log_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    version = _version_for_user(db, log_id, user)
    confirm_daily_log(db, version, user.id)
    return daily_log_out(db, version)


@router.get(
    "/daily-logs/{log_id}/versions",
    response_model=list[DailyLogVersionSummary],
    summary="读取同一日志的全部版本",
)
def read_daily_log_versions(
    log_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    version = _version_for_user(db, log_id, user)
    return version_summaries(db, version.document_id)
