"""
실제 LLM 워크플로우 테스트 (vLLM/Ollama 연결)
- 실제 서버 환경에서 judge_speaking 함수 호출
- 정상 케이스 및 에러 시뮬레이션
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from api.speaking.speaking_service import SpeakingService
from loguru import logger


def test_real_workflow():
    """실제 LLM 연결 테스트 (vLLM/Ollama)"""
    print("\n" + "="*60)
    print("🧪 실제 LLM 워크플로우 테스트")
    print("="*60)
    
    # SpeakingService 인스턴스 생성
    service = SpeakingService()
    
    # 테스트 케이스
    test_cases = [
        {
            "name": "정상 케이스 - 간단한 인사",
            "question": "안녕하세요, 성함이 어떻게 되세요?",
            "answer": "저는 김철수입니다."
        },
        {
            "name": "정상 케이스 - 입국 심사",
            "question": "어디서 오셨습니까?",
            "answer": "저는 한국에서 왔습니다."
        }
    ]
    
    for case in test_cases:
        print(f"\n📦 {case['name']}")
        print("-" * 40)
        print(f"   질문: {case['question']}")
        print(f"   답변: {case['answer']}")
        
        try:
            result = service.judge_speaking(case['question'], case['answer'])
            
            if result:
                # 결과 분석
                grammar_result = result.get('grammar_result') or {}
                context_result = result.get('context_result') or {}
                score_result = result.get('score_result') or {}
                
                grammar_score = grammar_result.get('grammar_score')
                context_score = context_result.get('context_score')
                final_score = score_result.get('score')
                final_feedback = result.get('final_feedback')
                
                # 시스템 오류 확인
                is_grammar_error = grammar_result.get('status') == 'SYSTEM_ERROR'
                is_context_error = context_result.get('status') == 'SYSTEM_ERROR'
                is_score_error = score_result.get('result') == 'SYSTEM_ERROR'
                
                print(f"\n📊 결과:")
                print(f"   문법 점수: {grammar_score} {'(SYSTEM_ERROR)' if is_grammar_error else ''}")
                print(f"   맥락 점수: {context_score} {'(SYSTEM_ERROR)' if is_context_error else ''}")
                print(f"   최종 점수: {final_score} {'(SYSTEM_ERROR)' if is_score_error else ''}")
                print(f"   피드백: {str(final_feedback)[:100]}...")
                
                if is_grammar_error or is_context_error or is_score_error:
                    print(f"\n⚠️ 시스템 오류가 발생했지만 Fallback이 정상 동작함")
                else:
                    print(f"\n✅ 정상 평가 완료!")
            else:
                print(f"\n❌ 결과 없음")
                
        except Exception as e:
            print(f"\n❌ 예외 발생: {type(e).__name__}: {e}")
    
    print("\n" + "="*60)
    print("🎯 테스트 완료")
    print("="*60)


if __name__ == "__main__":
    test_real_workflow()
