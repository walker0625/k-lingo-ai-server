"""
Multi-Agent 노드 실패 처리 테스트
- LLM 실패 시뮬레이션
- 재시도 로직 검증
- Fallback 결과 생성 검증
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import MagicMock, patch
from agent.judge.states import AssessmentState
from agent.judge.nodes.analysts import linguistic_analyst, context_analyst, NodeErrorType
from agent.judge.nodes.evaluator import chief_evaluator
from agent.judge.nodes.tutor import feedback_tutor
from agent.judge.supervisor import supervisor_node, MAX_RETRY_COUNT, _create_fallback_result


def create_test_state() -> AssessmentState:
    """테스트용 기본 상태 생성"""
    return {
        "user_text": "안녕하세요",
        "question": "자기소개를 해주세요",
        "context": "한국어 학습 상황",
        "target_level": 2,
        "grammar_result": None,
        "context_result": None,
        "score_result": None,
        "final_feedback": None,
        "next_worker": None,
        "revision_count": 0,
        "error_states": None,
        "retry_counts": None
    }


class TestLinguistNodeFailure:
    """Linguist 노드 실패 테스트"""
    
    def test_llm_timeout_sets_error_state(self):
        """LLM 타임아웃 시 error_states가 설정되는지 확인"""
        state = create_test_state()
        
        # LLM 호출이 TimeoutError를 발생시키도록 모킹
        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = TimeoutError("Connection timed out")
        
        result = linguistic_analyst(state, mock_llm)
        
        assert result["grammar_result"] is None, "실패 시 grammar_result는 None이어야 함"
        assert result["error_states"]["linguist"] == NodeErrorType.LLM_TIMEOUT, "에러 타입이 LLM_TIMEOUT이어야 함"
        assert result["retry_counts"]["linguist"] == 1, "재시도 횟수가 1이어야 함"
        print("✅ test_llm_timeout_sets_error_state PASSED")
    
    def test_llm_api_error_sets_error_state(self):
        """LLM API 오류 시 error_states가 설정되는지 확인"""
        state = create_test_state()
        
        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = Exception("API Error: Rate limit exceeded")
        
        result = linguistic_analyst(state, mock_llm)
        
        assert result["grammar_result"] is None
        assert result["error_states"]["linguist"] == NodeErrorType.LLM_API_ERROR
        assert result["retry_counts"]["linguist"] == 1
        print("✅ test_llm_api_error_sets_error_state PASSED")


class TestContextAnalystNodeFailure:
    """Context Analyst 노드 실패 테스트"""
    
    def test_llm_timeout_sets_error_state(self):
        """LLM 타임아웃 시 error_states가 설정되는지 확인"""
        state = create_test_state()
        
        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = TimeoutError("Connection timed out")
        
        result = context_analyst(state, mock_llm)
        
        assert result["context_result"] is None
        assert result["error_states"]["context_analyst"] == NodeErrorType.LLM_TIMEOUT
        assert result["retry_counts"]["context_analyst"] == 1
        print("✅ test_context_analyst_timeout PASSED")


class TestTutorNodeFailure:
    """Tutor 노드 실패 테스트"""
    
    def test_llm_timeout_sets_error_state(self):
        """LLM 타임아웃 시 error_states가 설정되는지 확인"""
        state = create_test_state()
        state["score_result"] = {"score": 70, "result": "Pass"}
        
        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = TimeoutError("Connection timed out")
        
        result = feedback_tutor(state, mock_llm)
        
        assert result["final_feedback"] is None
        assert result["error_states"]["tutor"] == NodeErrorType.LLM_TIMEOUT
        assert result["retry_counts"]["tutor"] == 1
        print("✅ test_tutor_timeout PASSED")


class TestEvaluatorNodeFailure:
    """Evaluator 노드 실패 테스트"""
    
    def test_invalid_score_data_handling(self):
        """잘못된 점수 데이터 처리 확인"""
        state = create_test_state()
        state["grammar_result"] = {"grammar_score": "invalid"}  # 숫자가 아닌 값
        state["context_result"] = {"context_score": 70}
        
        mock_llm = MagicMock()
        result = chief_evaluator(state, mock_llm)
        
        # 에러 발생 시 fallback 결과 반환 (score: None, status: SYSTEM_ERROR)
        assert result["score_result"] is not None
        assert result["score_result"]["is_fallback"] == True
        assert result["score_result"]["score"] is None, "실패 시 score는 None이어야 함"
        assert result["score_result"]["result"] == "SYSTEM_ERROR"
        print("✅ test_evaluator_invalid_data PASSED")


class TestSupervisorRetryLogic:
    """Supervisor 재시도 로직 테스트"""
    
    def test_retry_on_first_failure(self):
        """첫 번째 실패 시 재시도 명령 확인"""
        state = create_test_state()
        state["error_states"] = {"linguist": NodeErrorType.LLM_TIMEOUT}
        state["retry_counts"] = {"linguist": 1}
        
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = '{"next_worker": "FINISH"}'
        mock_llm.invoke.return_value = mock_response
        
        result = supervisor_node(state, mock_llm)
        
        assert result["next_worker"] == "linguist", "실패한 노드로 재시도해야 함"
        print("✅ test_retry_on_first_failure PASSED")
    
    def test_fallback_after_max_retries(self):
        """최대 재시도 후 Fallback 결과 반환 확인"""
        state = create_test_state()
        state["error_states"] = {"linguist": NodeErrorType.LLM_TIMEOUT}
        state["retry_counts"] = {"linguist": MAX_RETRY_COUNT}  # 최대 횟수 도달
        
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = '{"next_worker": "FINISH"}'
        mock_llm.invoke.return_value = mock_response
        
        result = supervisor_node(state, mock_llm)
        
        # Fallback 결과가 포함되어야 함 (score: None, status: SYSTEM_ERROR)
        assert "grammar_result" in result, "Fallback grammar_result가 있어야 함"
        assert result["grammar_result"]["is_fallback"] == True
        assert result["grammar_result"]["grammar_score"] is None, "실패 시 score는 None이어야 함"
        assert result["grammar_result"]["status"] == "SYSTEM_ERROR"
        print("✅ test_fallback_after_max_retries PASSED")


class TestFallbackResults:
    """Fallback 결과 생성 테스트"""
    
    def test_linguist_fallback(self):
        """Linguist Fallback 결과 확인 (score: None, status: SYSTEM_ERROR)"""
        fallback = _create_fallback_result("linguist")
        assert fallback["grammar_result"]["grammar_score"] is None, "실패 시 score는 None"
        assert fallback["grammar_result"]["status"] == "SYSTEM_ERROR"
        assert fallback["grammar_result"]["is_fallback"] == True
        print("✅ test_linguist_fallback PASSED")
    
    def test_context_analyst_fallback(self):
        """Context Analyst Fallback 결과 확인 (score: None, status: SYSTEM_ERROR)"""
        fallback = _create_fallback_result("context_analyst")
        assert fallback["context_result"]["context_score"] is None, "실패 시 score는 None"
        assert fallback["context_result"]["status"] == "SYSTEM_ERROR"
        assert fallback["context_result"]["is_fallback"] == True
        print("✅ test_context_analyst_fallback PASSED")
    
    def test_evaluator_fallback(self):
        """Evaluator Fallback 결과 확인 (score: None, status: SYSTEM_ERROR)"""
        fallback = _create_fallback_result("evaluator")
        assert fallback["score_result"]["score"] is None, "실패 시 score는 None"
        assert fallback["score_result"]["result"] == "SYSTEM_ERROR"
        assert fallback["score_result"]["status"] == "EVALUATION_FAILED"
        assert fallback["score_result"]["is_fallback"] == True
        print("✅ test_evaluator_fallback PASSED")
    
    def test_tutor_fallback(self):
        """Tutor Fallback 결과 확인"""
        fallback = _create_fallback_result("tutor")
        assert "final_feedback" in fallback
        assert fallback["feedback_status"] == "SYSTEM_ERROR"
        assert fallback["is_fallback"] == True
        print("✅ test_tutor_fallback PASSED")


def run_all_tests():
    """모든 테스트 실행"""
    print("\n" + "="*60)
    print("🧪 Multi-Agent 노드 실패 처리 테스트 시작")
    print("="*60 + "\n")
    
    test_classes = [
        TestLinguistNodeFailure,
        TestContextAnalystNodeFailure, 
        TestTutorNodeFailure,
        TestEvaluatorNodeFailure,
        TestSupervisorRetryLogic,
        TestFallbackResults
    ]
    
    passed = 0
    failed = 0
    
    for test_class in test_classes:
        print(f"\n📦 {test_class.__name__}")
        print("-" * 40)
        
        instance = test_class()
        for method_name in dir(instance):
            if method_name.startswith("test_"):
                try:
                    getattr(instance, method_name)()
                    passed += 1
                except AssertionError as e:
                    print(f"❌ {method_name} FAILED: {e}")
                    failed += 1
                except Exception as e:
                    print(f"❌ {method_name} ERROR: {type(e).__name__}: {e}")
                    failed += 1
    
    print("\n" + "="*60)
    print(f"🎯 테스트 결과: {passed} passed, {failed} failed")
    print("="*60 + "\n")
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
