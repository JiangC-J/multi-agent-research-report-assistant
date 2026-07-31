from pydantic import BaseModel, Field

from app.schemas.claim import ClaimResponse


class AnalystExecutionResponse(BaseModel):
    """
    Analyst 执行完成后的结果。
    """

    input_evidence_count: int = Field(
        ...,
        ge=0,
        description="本次传入 Analyst 的 Evidence 数量。",
    )
    saved_claims: list[ClaimResponse] = Field(
        default_factory=list,
        description="本次成功保存的 Claim。",
    )