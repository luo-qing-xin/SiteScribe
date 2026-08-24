from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from .auth import hash_password
from .db import SessionLocal
from .models import Project, ProjectLocation, ProjectMember, SiteRecord, Task, User

USERS = [
    {"username": "zhangwei", "name": "张伟", "role": "安全员", "organization": "XX建设集团", "department": "安全部", "crew": None},
    {"username": "wangqiang", "name": "王强", "role": "施工员", "organization": "XX建设集团", "department": "工程部", "crew": None},
    {"username": "lijianguo", "name": "李建国", "role": "班组长", "organization": "XX劳务公司", "department": None, "crew": "钢筋班组"},
]
ZONES = ["东侧", "西侧", "南侧", "北侧", "核心区", "其他"]
BUILDINGS = {"1号楼": 3, "2号楼": 3, "3号楼": 6}


def seed() -> None:
    now = datetime.now(UTC)
    with SessionLocal() as db:
        users = {}
        for data in USERS:
            user = db.scalar(select(User).where(User.username == data["username"]))
            if not user:
                user = User(**data, password_hash=hash_password("demo123"))
                db.add(user)
                db.flush()
            users[data["username"]] = user

        project = db.scalar(select(Project).where(Project.name == "海悦花园项目"))
        if not project:
            project = Project(name="海悦花园项目", organization="XX建设集团", address="广州市", status="施工中")
            db.add(project)
            db.flush()
        for user in users.values():
            if not db.scalar(select(ProjectMember).where(ProjectMember.project_id == project.id, ProjectMember.user_id == user.id)):
                db.add(ProjectMember(project_id=project.id, user_id=user.id))

        locations = {}
        for building, floor_count in BUILDINGS.items():
            for floor_number in range(1, floor_count + 1):
                for zone in ZONES:
                    key = (building, f"{floor_number}层", zone)
                    location = db.scalar(select(ProjectLocation).where(
                        ProjectLocation.project_id == project.id,
                        ProjectLocation.building == key[0],
                        ProjectLocation.floor == key[1],
                        ProjectLocation.zone == key[2],
                    ))
                    if not location:
                        location = ProjectLocation(project_id=project.id, building=key[0], floor=key[1], zone=key[2])
                        db.add(location)
                        db.flush()
                    locations[key] = location

        if not db.scalar(select(SiteRecord).where(SiteRecord.project_id == project.id)):
            demos = [
                ("安全巡查", "巡查发现临边防护完整，安全通道畅通。", "1号楼", "2层", "东侧"),
                ("施工进度", "3号楼六层钢筋绑扎正在进行。", "3号楼", "6层", "西侧"),
                ("材料进场", "今日到场钢筋已按批次堆放并完成标识。", "2号楼", "1层", "南侧"),
                ("质量检查", "模板垂直度完成现场复核。", "1号楼", "3层", "核心区"),
            ]
            records = []
            for index, (category, description, building, floor, zone) in enumerate(demos):
                record = SiteRecord(
                    project_id=project.id,
                    recorder_id=users["zhangwei"].id if index % 2 == 0 else users["wangqiang"].id,
                    category=category,
                    description=description,
                    occurred_at=now - timedelta(hours=index * 4),
                    gps_status="not_requested",
                    location_id=locations[(building, floor, zone)].id,
                )
                db.add(record)
                records.append(record)
            db.flush()
            tasks = [
                Task(project_id=project.id, source_record_id=records[0].id, creator_id=users["zhangwei"].id, assignee_id=users["wangqiang"].id, title="补充安全通道标识", description="在1号楼二层东侧补充醒目标识。", due_at=now + timedelta(days=1), status="待处理"),
                Task(project_id=project.id, source_record_id=records[1].id, creator_id=users["wangqiang"].id, assignee_id=users["lijianguo"].id, title="完成六层钢筋自检", description="绑扎完成后提交班组自检结果。", due_at=now + timedelta(days=2), status="处理中"),
                Task(project_id=project.id, source_record_id=records[2].id, creator_id=users["zhangwei"].id, assignee_id=users["zhangwei"].id, title="核对材料合格证", description="核对本批钢筋合格证与批次。", due_at=now - timedelta(days=1), status="已完成"),
            ]
            db.add_all(tasks)
        db.commit()
    print("Seed complete: demo users, project, locations, records and tasks are ready.")


if __name__ == "__main__":
    seed()
