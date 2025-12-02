# backend/app/services/scoring/__init__.py

from typing import Any, Dict, Optional

# ดึง logic ใหม่มาใช้
from .scoring import get_default_weights, calculate_universal_score


def score_applicant(
    parsed_data: Dict[str, Any],
    weights_config: Optional[Dict[str, Any]] = None,
    job_description: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    wrapper ชื่อเดิม 'score_applicant' → ใช้ logic ใหม่ calculate_universal_score
    """
    if weights_config is None:
        weights_config = get_default_weights()

    return calculate_universal_score(
        parsed_data=parsed_data,
        weights_config=weights_config,
        job_description=job_description,
    )


class ScoringConfig:
    """
    dummy class ให้ import เดิมผ่านไปได้
    ถ้าภายหลังอยากใช้จริงค่อยมาออกแบบเพิ่ม
    """
    pass
