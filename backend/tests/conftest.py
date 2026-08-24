from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth import get_db, hash_password
from app.config import settings
from app.db import Base
from app.main import app
from app.models import Project, ProjectLocation, ProjectMember, User


@pytest.fixture()
def db(tmp_path: Path):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )

    @event.listens_for(engine, "connect")
    def foreign_keys(connection, _record):  # type: ignore[no-untyped-def]
        connection.execute("PRAGMA foreign_keys=ON")

    TestingSession = sessionmaker(bind=engine, expire_on_commit=False)
    Base.metadata.create_all(engine)
    session = TestingSession()
    password_hash = hash_password("demo123")
    member = User(username="member", password_hash=password_hash, name="成员", role="安全员", organization="测试单位")
    outsider = User(username="outsider", password_hash=password_hash, name="外部人员", role="施工员", organization="其他单位")
    project = Project(name="测试项目", organization="测试单位", address="广州", status="施工中")
    other_project = Project(name="其他项目", organization="其他单位", address="深圳", status="施工中")
    session.add_all([member, outsider, project, other_project])
    session.flush()
    session.add(ProjectMember(project_id=project.id, user_id=member.id))
    location = ProjectLocation(project_id=project.id, building="3号楼", floor="6层", zone="西侧")
    session.add(location)
    session.commit()
    settings.upload_dir = tmp_path / "uploads"
    settings.upload_dir.mkdir()

    def override_db():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_db] = override_db
    yield session
    app.dependency_overrides.clear()
    session.close()
    Base.metadata.drop_all(engine)


@pytest.fixture()
def client(db):
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def auth_client(client: TestClient):
    response = client.post("/api/auth/login", json={"username": "member", "password": "demo123"})
    assert response.status_code == 200
    return client


@pytest.fixture()
def project_data(db):
    project = db.query(Project).filter_by(name="测试项目").one()
    location = db.query(ProjectLocation).filter_by(project_id=project.id).one()
    member = db.query(User).filter_by(username="member").one()
    return project, location, member

