from fastapi import APIRouter, HTTPException, status, Path
from db.session import SessionDep  # 사용자 환경에 맞는 세션 의존성 임포트 가정
from api.evaluation.evaluation_service import EvaluationService
from api.evaluation.dto.evaluation_dto import EvaluationResponse
from loguru import logger

router = APIRouter()

@router.get('/rooms/{room_id}', response_model=EvaluationResponse, status_code=status.HTTP_200_OK)
def evaluate_learning_result(
    session: SessionDep,
    room_id: int = Path(..., title="방 번호", description="평가를 수행할 방의 고유 ID")
) -> EvaluationResponse:
    """
    특정 방(room_id)의 학습 데이터를 기반으로 AI 평가 결과를 생성합니다.
    """
    logger.info(f"Request: Evaluate Room ID {room_id}")

    try:
        service = EvaluationService()
        # session을 서비스로 전달하여 DB 조회를 수행하도록 함
        evaluation_result = service.evaluate_room(room_id, session)
        
        return evaluation_result
    
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"평가 프로세스 실패: {e}")
        raise HTTPException(status_code=500, detail="평가 처리 중 알 수 없는 오류가 발생했습니다")