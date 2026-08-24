import io
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from fastapi import Depends, FastAPI, File, HTTPException, Query, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from PIL import Image, UnidentifiedImageError
from sqlalchemy.orm import Session, joinedload

from .auth import create_token, current_user, get_db, require_member, verify_password
from .config import settings
from .models import MediaFile, Project, ProjectLocation, ProjectMember, SiteRecord, Task, User
from .schemas import (
    DashboardOut,
    LocationOut,
    LoginIn,
    MessageOut,
    PhotoOut,
    ProjectOut,
    RecordCreate,
    RecordOut,
    RecordPatch,
    TaskCreate,
    TaskOut,
    TaskPatch,
    UserOut,
)

app = FastAPI(title="工地小秘 API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
settings.upload_dir.mkdir(parents=True, exist_ok=True)

RECORD_LOAD = (
    joinedload(SiteRecord.recorder),
    joinedload(SiteRecord.project),
    joinedload(SiteRecord.location),
    joinedload(SiteRecord.photos),
)
TASK_LOAD = (joinedload(Task.creator), joinedload(Task.assignee))


@app.exception_handler(HTTPException)
async def http_error(_request, exc: HTTPException):  # type: ignore[no-untyped-def]
    from fastapi.responses import JSONResponse

    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.get("/api/health", response_model=MessageOut)
def health() -> MessageOut:
    return MessageOut(message="ok")


@app.post("/api/auth/login", response_model=UserOut)
def login(payload: LoginIn, response: Response, db: Session = Depends(get_db)) -> User:
    user = db.query(User).filter(User.username == payload.username).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    response.set_cookie(
        "access_token",
        create_token(user.id),
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=settings.jwt_expire_hours * 3600,
        path="/",
    )
    return user


@app.post("/api/auth/logout", response_model=MessageOut)
def logout(response: Response) -> MessageOut:
    response.delete_cookie("access_token", path="/")
    return MessageOut(message="已退出登录")


@app.get("/api/auth/me", response_model=UserOut)
def me(user: User = Depends(current_user)) -> User:
    return user


@app.get("/api/projects", response_model=list[ProjectOut])
def projects(user: User = Depends(current_user), db: Session = Depends(get_db)) -> list[Project]:
    return (
        db.query(Project)
        .join(ProjectMember)
        .filter(ProjectMember.user_id == user.id)
        .order_by(Project.id)
        .all()
    )


@app.get("/api/projects/{project_id}", response_model=ProjectOut)
def project(project_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    require_member(db, user.id, project_id)
    item = db.get(Project, project_id)
    if not item:
        raise HTTPException(status_code=404, detail="项目不存在")
    return item


@app.get("/api/projects/{project_id}/members", response_model=list[UserOut])
def members(project_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    require_member(db, user.id, project_id)
    return (
        db.query(User)
        .join(ProjectMember)
        .filter(ProjectMember.project_id == project_id)
        .order_by(User.id)
        .all()
    )


@app.get("/api/projects/{project_id}/locations", response_model=list[LocationOut])
def locations(project_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    require_member(db, user.id, project_id)
    return (
        db.query(ProjectLocation)
        .filter(ProjectLocation.project_id == project_id)
        .order_by(ProjectLocation.id)
        .all()
    )


def record_query(db: Session):
    return db.query(SiteRecord).options(*RECORD_LOAD)


def task_query(db: Session):
    return db.query(Task).options(*TASK_LOAD)


@app.get("/api/projects/{project_id}/dashboard", response_model=DashboardOut)
def dashboard(project_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    require_member(db, user.id, project_id)
    now = datetime.now(UTC)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow = today + timedelta(days=1)
    records = record_query(db).filter(SiteRecord.project_id == project_id)
    tasks = task_query(db).filter(Task.project_id == project_id)
    return DashboardOut(
        today_records=records.filter(
            SiteRecord.occurred_at >= today, SiteRecord.occurred_at < tomorrow
        ).count(),
        pending_tasks=tasks.filter(Task.status.in_(["待处理", "处理中"])).count(),
        completed_tasks=tasks.filter(Task.status == "已完成").count(),
        recent_records=records.order_by(SiteRecord.occurred_at.desc()).limit(5).all(),
        upcoming_tasks=tasks.filter(
            Task.status.in_(["待处理", "处理中"]), Task.due_at >= now
        ).order_by(Task.due_at).limit(5).all(),
    )


@app.get("/api/records", response_model=list[RecordOut])
def list_records(
    project_id: int,
    category: str | None = None,
    today_only: bool = False,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    require_member(db, user.id, project_id)
    query = record_query(db).filter(SiteRecord.project_id == project_id)
    if category:
        query = query.filter(SiteRecord.category == category)
    if today_only:
        now = datetime.now(UTC)
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        query = query.filter(SiteRecord.occurred_at >= start, SiteRecord.occurred_at < start + timedelta(days=1))
    return query.order_by(SiteRecord.occurred_at.desc()).all()


def validate_location(db: Session, project_id: int, location_id: int) -> ProjectLocation:
    location = db.get(ProjectLocation, location_id)
    if not location or location.project_id != project_id:
        raise HTTPException(status_code=422, detail="所选位置不属于当前项目")
    return location


@app.post("/api/records", response_model=RecordOut, status_code=201)
def create_record(
    payload: RecordCreate, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    require_member(db, user.id, payload.project_id)
    validate_location(db, payload.project_id, payload.location_id)
    item = SiteRecord(**payload.model_dump(), recorder_id=user.id)
    db.add(item)
    db.commit()
    return record_query(db).filter(SiteRecord.id == item.id).one()


def get_record_for_user(db: Session, record_id: int, user: User) -> SiteRecord:
    item = record_query(db).filter(SiteRecord.id == record_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="现场记录不存在")
    require_member(db, user.id, item.project_id)
    return item


@app.get("/api/records/{record_id}", response_model=RecordOut)
def get_record(record_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return get_record_for_user(db, record_id, user)


@app.patch("/api/records/{record_id}", response_model=RecordOut)
def update_record(
    record_id: int,
    payload: RecordPatch,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    item = get_record_for_user(db, record_id, user)
    changes = payload.model_dump(exclude_unset=True)
    if "location_id" in changes:
        validate_location(db, item.project_id, changes["location_id"])
    for key, value in changes.items():
        setattr(item, key, value)
    db.commit()
    return get_record_for_user(db, record_id, user)


@app.delete("/api/records/{record_id}", response_model=MessageOut)
def delete_record(record_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    item = get_record_for_user(db, record_id, user)
    paths = [settings.upload_dir.parent / photo.relative_path for photo in item.photos]
    db.delete(item)
    db.commit()
    for path in paths:
        path.unlink(missing_ok=True)
    return MessageOut(message="现场记录已删除")


FORMAT_MIME = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}
MAX_PHOTO_SIZE = 10 * 1024 * 1024


@app.post("/api/records/{record_id}/photos", response_model=list[PhotoOut], status_code=201)
def upload_photos(
    record_id: int,
    files: list[UploadFile] = File(...),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    item = get_record_for_user(db, record_id, user)
    if not files or len(files) + len(item.photos) > 9:
        raise HTTPException(status_code=422, detail="每条记录最多上传 9 张照片")
    validated: list[tuple[UploadFile, bytes, str, str]] = []
    for upload in files:
        data = upload.file.read(MAX_PHOTO_SIZE + 1)
        if len(data) > MAX_PHOTO_SIZE:
            raise HTTPException(status_code=413, detail="单张照片不能超过 10MB")
        try:
            with Image.open(io.BytesIO(data)) as image:
                image.verify()
                image_format = image.format
        except (UnidentifiedImageError, OSError) as exc:
            raise HTTPException(status_code=422, detail="仅支持有效的 JPEG、PNG、WebP 图片") from exc
        if image_format not in FORMAT_MIME:
            raise HTTPException(status_code=422, detail="仅支持 JPEG、PNG、WebP 图片")
        extension = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}[image_format]
        validated.append((upload, data, extension, FORMAT_MIME[image_format]))
    created: list[MediaFile] = []
    try:
        for upload, data, extension, mime in validated:
            stored_name = f"{uuid4().hex}{extension}"
            path = settings.upload_dir / stored_name
            path.write_bytes(data)
            media = MediaFile(
                site_record_id=item.id,
                original_name=Path(upload.filename or "photo").name[:255],
                stored_name=stored_name,
                relative_path=f"uploads/{stored_name}",
                mime_type=mime,
                size_bytes=len(data),
            )
            db.add(media)
            created.append(media)
        db.commit()
    except Exception:
        db.rollback()
        for media in created:
            (settings.upload_dir / media.stored_name).unlink(missing_ok=True)
        raise
    return created


def get_photo_for_user(db: Session, photo_id: int, user: User) -> MediaFile:
    photo = db.get(MediaFile, photo_id)
    if not photo:
        raise HTTPException(status_code=404, detail="照片不存在")
    record = db.get(SiteRecord, photo.site_record_id)
    if not record:
        raise HTTPException(status_code=404, detail="现场记录不存在")
    require_member(db, user.id, record.project_id)
    return photo


@app.delete("/api/photos/{photo_id}", response_model=MessageOut)
def delete_photo(photo_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    photo = get_photo_for_user(db, photo_id, user)
    path = settings.upload_dir.parent / photo.relative_path
    db.delete(photo)
    db.commit()
    path.unlink(missing_ok=True)
    return MessageOut(message="照片已删除")


@app.get("/api/photos/{photo_id}/content")
def photo_content(photo_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    photo = get_photo_for_user(db, photo_id, user)
    path = settings.upload_dir.parent / photo.relative_path
    if not path.is_file():
        raise HTTPException(status_code=404, detail="照片文件不存在")
    return FileResponse(path, media_type=photo.mime_type, filename=photo.stored_name)


@app.get("/api/tasks", response_model=list[TaskOut])
def list_tasks(
    project_id: int,
    task_status: str | None = Query(None, alias="status"),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    require_member(db, user.id, project_id)
    query = task_query(db).filter(Task.project_id == project_id)
    if task_status:
        query = query.filter(Task.status == task_status)
    return query.order_by(Task.created_at.desc()).all()


def validate_task_refs(db: Session, payload: TaskCreate) -> None:
    assignee = db.query(ProjectMember).filter_by(
        project_id=payload.project_id, user_id=payload.assignee_id
    ).first()
    if not assignee:
        raise HTTPException(status_code=422, detail="责任人必须是当前项目成员")
    if payload.source_record_id:
        record = db.get(SiteRecord, payload.source_record_id)
        if not record or record.project_id != payload.project_id:
            raise HTTPException(status_code=422, detail="来源记录不属于当前项目")


@app.post("/api/tasks", response_model=TaskOut, status_code=201)
def create_task(payload: TaskCreate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    require_member(db, user.id, payload.project_id)
    validate_task_refs(db, payload)
    item = Task(**payload.model_dump(), creator_id=user.id)
    db.add(item)
    db.commit()
    return task_query(db).filter(Task.id == item.id).one()


def get_task_for_user(db: Session, task_id: int, user: User) -> Task:
    item = task_query(db).filter(Task.id == task_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="待办不存在")
    require_member(db, user.id, item.project_id)
    return item


@app.get("/api/tasks/{task_id}", response_model=TaskOut)
def get_task(task_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return get_task_for_user(db, task_id, user)


@app.patch("/api/tasks/{task_id}", response_model=TaskOut)
def update_task(
    task_id: int,
    payload: TaskPatch,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    item = get_task_for_user(db, task_id, user)
    changes = payload.model_dump(exclude_unset=True)
    if "assignee_id" in changes:
        member = db.query(ProjectMember).filter_by(
            project_id=item.project_id, user_id=changes["assignee_id"]
        ).first()
        if not member:
            raise HTTPException(status_code=422, detail="责任人必须是当前项目成员")
    for key, value in changes.items():
        setattr(item, key, value)
    db.commit()
    return get_task_for_user(db, task_id, user)


@app.delete("/api/tasks/{task_id}", response_model=MessageOut)
def delete_task(task_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    item = get_task_for_user(db, task_id, user)
    db.delete(item)
    db.commit()
    return MessageOut(message="待办已删除")
