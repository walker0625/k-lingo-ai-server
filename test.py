import sys
import os
import logging
from pathlib import Path
from langchain_community.chat_models import ChatOllama

# [1] 경로 설정 (Agent 모듈을 찾기 위해 필수)
# 현재 파일 위치를 기준으로 'agent/judge' 경로를 sys.path에 추가합니다.
current_dir = Path(__file__).resolve().parent
sys.path.append(str(current_dir))

# LangGraph 모듈 임포트 전에 로거를 초기화해야 LangGraph의 상태 노드에 로거가 주입됩니다.
# (agent/judge/logger.py 파일이 있다고 가정합니다.)
try:
    from agent.judge.workflow import create_assessment_graph
    from agent.judge.states import AssessmentState
    from agent.judge.logger import get_logger
except ImportError as e:
    print(f"\n[❌ 임포트 에러]: {e}")
    print("Agent 모듈 경로 설정이 잘못되었을 수 있습니다. 'agent/judge' 폴더 구조를 확인하세요.")
    sys.exit(1)

# [2] 로거 설정 (테스트 파일 로거)
logger = get_logger("TestRunner")
logger.setLevel(logging.INFO) # 기본 실행 로그는 INFO 레벨

def run_test():
    """LangGraph 에이전트 워크플로우를 실행합니다."""
    
    # 1. LLM 설정 (JSON 모드 및 낮은 온도 설정)
    try:
        # EXAONE 모델 사용 시 Ollama 호환성 및 JSON 모드 필수
        llm = ChatOllama(
            # qwen:14b-chat - 제미나이 추천
            # llama3:8b-instruct-q4_K_M - 제미나이 추천
            # qwen3-vl:8b - 응답이 없음 : 양자화 모델 변경 test           
            # deepseek-r1:8b - 응답이 없음 : 양자화 모델 변경 test           
            model="llama3:8b-instruct-q4_K_M",
            format="json",
            temperature=0.0,
            num_gpu=-1 # -1 : gpu 사용하도록 설정 / 0 : cpu 사용하도록 설정
        )
    except Exception as e:
        logger.error(f"❌ LLM 설정 실패: Ollama 서버가 실행 중인지, 모델이 설치되었는지 확인하세요. 에러: {e}")
        return

    # 2. 그래프 생성
    app = create_assessment_graph(llm)

    # 3. 입력 데이터 (AssessmentState의 모든 키를 포함하도록 초기화)
    inputs: AssessmentState = {
        "user_text": "경주 여행을 하러왔어",
        "question": "한국에 왜 오셨습니까?",
        "context": "입국 심사 (공적 상황)",
        "target_level": 2, # 2급 기준 평가
        
        # [디버깅 핵심] 모든 상태를 None/초기값으로 명시
        "grammar_result": None,
        "context_result": None,
        "score_result": None,
        "final_feedback": None,
        "next_worker": None,
        "revision_count": 0
    }

    logger.info("========================================")
    logger.info("🚀 K-Lingo 평가 에이전트 실행 중...")
    logger.info(f"사용자 입력: {inputs['user_text']} (목표 {inputs['target_level']}급)")
    logger.info("========================================")

    # 4. 실행 및 결과 출력
    result = None
    try:
        # recursion_limit을 설정하여 무한 루프 시 강제 종료 (디버깅에 도움)
        result = app.invoke(inputs, config={"recursion_limit": 30}) 
        
        # 결과 출력 시 .get() 메서드를 사용하여 KeyError 방지
        final_score = result.get('score_result', {}).get('score', 'N/A')
        final_feedback = result.get('final_feedback', '피드백이 생성되지 않음')
        
        logger.info("========================================")
        logger.info(f"✅ 최종 평가 완료: 점수 {final_score}")
        logger.info(f"피드백: {final_feedback.strip()}")
        logger.info("========================================")

    except Exception as e:
        logger.error(f"\n[❌ LangGraph 실행 중 심각한 에러 발생]: {e}")
        logger.error("이 에러는 보통 LLM의 출력 문제나 그래프 구성 오류로 발생합니다.")
        if result:
            # 에러 발생 직전의 상태를 출력하여 어느 노드에서 멈췄는지 추적
            logger.error(f"마지막 상태: {result.get('next_worker', 'N/A')}")
        
    return result

if __name__ == "__main__":
    run_test()