from typing import Protocol
from uuid import UUID

from app.schemas.evidence import EvidenceResponse


class EvidenceRepository(Protocol):
    """
    证据数据访问的抽象约定。
    """

    def create(self, evidence: EvidenceResponse) -> EvidenceResponse:
        """
        保存一条新的证据记录。
        """

    def exists_by_task_subtask_and_url(
        self,
        task_id: UUID,
        subtask_id: str,
        source_url: str,
    ) -> bool:
        """
        检查指定子任务下是否已存在同一来源链接。
        """

    def list_by_task_id(self, task_id: UUID) -> list[EvidenceResponse]:
        """
        查询一个研究任务的全部证据。
        """