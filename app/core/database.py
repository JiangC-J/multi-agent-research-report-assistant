from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATABASE_PATH = PROJECT_ROOT / "research_assistant.db"
DATABASE_URL = f"sqlite:///{DATABASE_PATH.as_posix()}"


engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)


class Base(DeclarativeBase):
    """
    所有 SQLAlchemy 数据库模型的基类。
    """


def init_db() -> None:
    """
    创建尚不存在的数据库表。

    第一版使用 create_all 简化开发。
    后续接入 PostgreSQL 时会使用 Alembic 管理数据库迁移。
    """
    from app.models.agent_run import AgentRunModel  # noqa: F401
    from app.models.claim import ClaimEvidenceModel, ClaimModel  # noqa: F401
    from app.models.evidence import EvidenceModel  # noqa: F401
    from app.models.report import ReportModel  # noqa: F401
    from app.models.research_plan import (  # noqa: F401
        ResearchPlanModel,
        ResearchSubTaskModel,
    )
    from app.models.research_task import ResearchTaskModel  # noqa: F401
    from app.models.workflow_run import WorkflowRunModel  # noqa: F401
    from app.models.review import ClaimReviewModel  # noqa: F401

    Base.metadata.create_all(bind=engine)