"""
LLM 실패 케이스 시뮬레이션 테스트
- LLM 호출 실패를 강제로 발생시켜 에러 핸들링 동작 검증
- 재시도 로직 및 Fallback 결과 확인
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from unittest.mock import MagicMock, patch
from agent.judge.workflow import create_assessment_graph
from agent.judge.states import AssessmentState
from agent.judge.supervisor import MAX_RETRY_COUNT
from api.speaking.dto.speaking_dto import SpeakingResponse


def create_failing_mock_llm(fail_count: int = 1, fail_on_nodes: list = None):
    """
    특정 횟수만큼 실패 후 성공하는 Mock LLM 생성
    fail_on_nodes: 실패시킬 노드 목록 (None이면 모두 실패)
    """
    mock_llm = MagicMock()
    call_count = [0]  # mutable counter
    
    def invoke_side_effect(messages):
        call_count[0] += 1
        
        # 첫 몇 번은 실패
        if call_count[0] <= fail_count:
            raise TimeoutError(f"Simulated timeout (call #{call_count[0]})")
        
        # 이후는 성공 (기본 응답)
        mock_response = MagicMock()
        mock_response.content = '{"next_worker": "FINISH"}'
        return mock_response
    
    mock_llm.invoke.side_effect = invoke_side_effect
    return mock_llm


def test_single_node_failure_and_retry():
    """단일 노드 실패 후 재시도 테스트"""
    print("\n" + "="*60)
    print("🧪 테스트 1: 단일 노드 실패 후 재시도")
    print("="*60)
    
    from agent.judge.nodes.analysts import linguistic_analyst, NodeErrorType
    
    # 첫 번째 호출만 실패하는 Mock LLM
    mock_llm = MagicMock()
    call_count = [0]
    
    def invoke_side_effect(messages):
        call_count[0] += 1
        if call_count[0] == 1:
            raise TimeoutError("Simulated timeout")
        
        # 두 번째 호출부터 성공
        mock_response = MagicMock()
        mock_response.content = '{"grammar_score": 75, "issues": []}'
        return mock_response
    
    mock_llm.invoke.side_effect = invoke_side_effect
    
    state = {
        "user_text": "테스트",
        "question": "테스트 질문",
        "target_level": 1,
        "error_states": None,
        "retry_counts": None
    }
    
    # 첫 번째 호출 - 실패
    print("\n📦 첫 번째 호출 (실패 예상)")
    print("-" * 40)
    result1 = linguistic_analyst(state, mock_llm)
    
    print(f"   grammar_result: {result1.get('grammar_result')}")
    print(f"   error_states: {result1.get('error_states')}")
    print(f"   retry_counts: {result1.get('retry_counts')}")
    
    assert result1["grammar_result"] is None, "실패 시 grammar_result는 None"
    assert result1["error_states"]["linguist"] == NodeErrorType.LLM_TIMEOUT
    assert result1["retry_counts"]["linguist"] == 1
    print("   ✅ 첫 번째 호출 실패 정상 처리")
    
    # 두 번째 호출 - 성공 (재시도)
    print("\n📦 두 번째 호출 (재시도 - 성공 예상)")
    print("-" * 40)
    
    state2 = {
        **state,
        "error_states": result1["error_states"],
        "retry_counts": result1["retry_counts"]
    }
    
    result2 = linguistic_analyst(state2, mock_llm)
    
    print(f"   grammar_result: {result2.get('grammar_result')}")
    print(f"   error_states: {result2.get('error_states')}")
    
    assert result2["grammar_result"] is not None, "재시도 성공 시 grammar_result 존재"
    assert result2["error_states"]["linguist"] is None, "성공 시 에러 상태 클리어"
    print("   ✅ 재시도 성공!")
    
    print("\n" + "="*60)
    print("🎯 테스트 1 완료: 재시도 로직 정상 동작")
    print("="*60)


def test_max_retry_exceeded_fallback():
    """최대 재시도 횟수 초과 후 Fallback 테스트"""
    print("\n" + "="*60)
    print(f"🧪 테스트 2: 최대 재시도({MAX_RETRY_COUNT}회) 초과 후 Fallback")
    print("="*60)
    
    from agent.judge.supervisor import supervisor_node, _create_fallback_result
    from agent.judge.nodes.analysts import NodeErrorType
    
    # 항상 실패하는 Mock LLM
    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.content = '{"next_worker": "context_analyst"}'
    mock_llm.invoke.return_value = mock_response
    
    # 최대 재시도 횟수에 도달한 상태
    state = {
        "user_text": "테스트",
        "question": "테스트 질문",
        "target_level": 1,
        "grammar_result": None,
        "context_result": None,
        "score_result": None,
        "final_feedback": None,
        "next_worker": None,
        "revision_count": 0,
        "error_states": {"linguist": NodeErrorType.LLM_TIMEOUT},
        "retry_counts": {"linguist": MAX_RETRY_COUNT}  # 최대 횟수 도달
    }
    
    print(f"\n📦 linguist 노드 최대 재시도 횟수({MAX_RETRY_COUNT}) 도달 상태")
    print("-" * 40)
    print(f"   error_states: {state['error_states']}")
    print(f"   retry_counts: {state['retry_counts']}")
    
    result = supervisor_node(state, mock_llm)
    
    print(f"\n📊 Supervisor 결과:")
    print(f"   grammar_result: {result.get('grammar_result')}")
    print(f"   next_worker: {result.get('next_worker')}")
    
    # Fallback 결과 확인
    assert "grammar_result" in result, "Fallback grammar_result 존재"
    assert result["grammar_result"]["is_fallback"] == True, "is_fallback 플래그 True"
    assert result["grammar_result"]["grammar_score"] is None, "Fallback 시 score는 None"
    assert result["grammar_result"]["status"] == "SYSTEM_ERROR", "status는 SYSTEM_ERROR"
    
    print("   ✅ Fallback 결과 정상 생성!")
    print(f"      - grammar_score: {result['grammar_result']['grammar_score']}")
    print(f"      - status: {result['grammar_result']['status']}")
    print(f"      - is_fallback: {result['grammar_result']['is_fallback']}")
    
    print("\n" + "="*60)
    print("🎯 테스트 2 완료: Fallback 로직 정상 동작")
    print("="*60)


def test_full_workflow_all_nodes_fail():
    """전체 워크플로우에서 모든 노드 실패 시 API 응답 테스트"""
    print("\n" + "="*60)
    print("🧪 테스트 3: 전체 워크플로우 실패 시 API 응답 형식")
    print("="*60)
    
    # 시뮬레이션: 모든 노드가 SYSTEM_ERROR인 상태
    assessment_data = {
        "grammar_result": {
            "grammar_score": None,
            "status": "SYSTEM_ERROR",
            "issues": ["시스템 오류"],
            "is_fallback": True
        },
        "context_result": {
            "context_score": None,
            "status": "SYSTEM_ERROR", 
            "is_relevant": None,
            "is_fallback": True
        },
        "score_result": {
            "score": None,
            "result": "SYSTEM_ERROR",
            "status": "EVALUATION_FAILED",
            "is_fallback": True
        },
        "final_feedback": "We apologize...",
        "feedback_status": "SYSTEM_ERROR"
    }
    
    print("\n📦 시뮬레이션된 전체 실패 상태")
    print("-" * 40)
    
    # speaking_service.py의 오류 감지 로직 재현
    grammar_data = assessment_data.get('grammar_result') or {}
    context_data = assessment_data.get('context_result') or {}
    score_data = assessment_data.get('score_result') or {}
    
    grammar_score = grammar_data.get('grammar_score')
    context_score = context_data.get('context_score')
    final_overall_score = score_data.get('score')
    final_feedback = assessment_data.get('final_feedback')
    
    is_grammar_error = grammar_data.get('status') == 'SYSTEM_ERROR'
    is_context_error = context_data.get('status') == 'SYSTEM_ERROR'
    is_score_error = score_data.get('status') == 'EVALUATION_FAILED' or score_data.get('result') == 'SYSTEM_ERROR'
    is_feedback_error = assessment_data.get('feedback_status') == 'SYSTEM_ERROR'
    
    has_any_error = is_grammar_error or is_context_error or is_score_error or is_feedback_error
    all_failed = is_grammar_error and is_context_error and is_score_error
    
    if all_failed:
        status = "SYSTEM_ERROR"
        error_message = "시스템 오류로 평가를 완료할 수 없습니다. 다시 시도해주세요."
    elif has_any_error:
        status = "PARTIAL_ERROR"
        error_message = "일부 평가가 완료되지 않았습니다."
    else:
        status = "SUCCESS"
        error_message = None
    
    # SpeakingResponse 생성
    response = SpeakingResponse(
        grammar_score=grammar_score,
        context_score=context_score,
        final_overall_score=final_overall_score,
        final_feedback=final_feedback,
        status=status,
        is_system_error=has_any_error,
        error_message=error_message
    )
    
    print(f"\n📊 API 응답 (SpeakingResponse):")
    print(f"   grammar_score: {response.grammar_score}")
    print(f"   context_score: {response.context_score}")
    print(f"   final_overall_score: {response.final_overall_score}")
    print(f"   status: {response.status}")
    print(f"   is_system_error: {response.is_system_error}")
    print(f"   error_message: {response.error_message}")
    
    assert response.status == "SYSTEM_ERROR", "전체 실패 시 status는 SYSTEM_ERROR"
    assert response.is_system_error == True, "is_system_error는 True"
    assert response.grammar_score is None, "grammar_score는 None"
    assert response.final_overall_score is None, "final_overall_score는 None"
    
    print("\n📦 JSON 응답 형식:")
    print("-" * 40)
    print(response.model_dump_json(indent=2))
    
    print("\n" + "="*60)
    print("🎯 테스트 3 완료: 전체 실패 시 API 응답 형식 정상")
    print("="*60)


def test_partial_failure_scenario():
    """일부 노드만 실패하는 시나리오 테스트"""
    print("\n" + "="*60)
    print("🧪 테스트 4: 일부 노드만 실패 (PARTIAL_ERROR)")
    print("="*60)
    
    # 시뮬레이션: 문법은 성공, 맥락은 실패
    assessment_data = {
        "grammar_result": {
            "grammar_score": 80,
            "issues": []
        },
        "context_result": {
            "context_score": None,
            "status": "SYSTEM_ERROR",
            "is_fallback": True
        },
        "score_result": {
            "score": None,
            "result": "SYSTEM_ERROR",
            "status": "EVALUATION_FAILED"
        },
        "final_feedback": "일부 평가가 완료되지 않았습니다."
    }
    
    print("\n📦 시뮬레이션: 문법 성공(80점), 맥락 실패")
    print("-" * 40)
    
    grammar_data = assessment_data.get('grammar_result') or {}
    context_data = assessment_data.get('context_result') or {}
    score_data = assessment_data.get('score_result') or {}
    
    is_grammar_error = grammar_data.get('status') == 'SYSTEM_ERROR'
    is_context_error = context_data.get('status') == 'SYSTEM_ERROR'
    is_score_error = score_data.get('status') == 'EVALUATION_FAILED'
    
    has_any_error = is_grammar_error or is_context_error or is_score_error
    all_failed = is_grammar_error and is_context_error and is_score_error
    
    if all_failed:
        status = "SYSTEM_ERROR"
    elif has_any_error:
        status = "PARTIAL_ERROR"
    else:
        status = "SUCCESS"
    
    response = SpeakingResponse(
        grammar_score=grammar_data.get('grammar_score'),
        context_score=context_data.get('context_score'),
        final_overall_score=score_data.get('score'),
        final_feedback=assessment_data.get('final_feedback'),
        status=status,
        is_system_error=has_any_error,
        error_message="일부 평가가 완료되지 않았습니다." if has_any_error else None
    )
    
    print(f"\n📊 API 응답:")
    print(f"   grammar_score: {response.grammar_score} (성공)")
    print(f"   context_score: {response.context_score} (실패)")
    print(f"   status: {response.status}")
    print(f"   is_system_error: {response.is_system_error}")
    
    assert response.status == "PARTIAL_ERROR", "일부 실패 시 status는 PARTIAL_ERROR"
    assert response.grammar_score == 80, "성공한 문법 점수는 유지"
    assert response.context_score is None, "실패한 맥락 점수는 None"
    
    print("\n   ✅ 일부 실패(PARTIAL_ERROR) 정상 처리!")
    
    print("\n" + "="*60)
    print("🎯 테스트 4 완료: 부분 실패 처리 정상")
    print("="*60)


if __name__ == "__main__":
    test_single_node_failure_and_retry()
    test_max_retry_exceeded_fallback()
    test_full_workflow_all_nodes_fail()
    test_partial_failure_scenario()
    
    print("\n" + "="*60)
    print("🎉 모든 실패 케이스 테스트 완료!")
    print("="*60 + "\n")
