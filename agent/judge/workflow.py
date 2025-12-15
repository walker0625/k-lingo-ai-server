# agent/judge/workflow.py
from langgraph.graph import StateGraph, END
from functools import partial
from .states import AssessmentState
from .nodes import analysts, evaluator, tutor
from .supervisor import supervisor_node

def create_assessment_graph(llm):
    """LangGraph 워크플로우 생성"""
    
    workflow = StateGraph(AssessmentState)
    
    # 노드 등록 (LLM과 로깅 주입)
    workflow.add_node("supervisor", partial(supervisor_node, llm=llm))
    workflow.add_node("linguist", partial(analysts.linguistic_analyst, llm=llm))
    workflow.add_node("context_analyst", partial(analysts.context_analyst, llm=llm))
    workflow.add_node("evaluator", partial(evaluator.chief_evaluator, llm=llm))
    workflow.add_node("tutor", partial(tutor.feedback_tutor, llm=llm))
    
    # 시작점 설정
    workflow.set_entry_point("supervisor")
    
    # 라우팅 로직
    workflow.add_conditional_edges(
        "supervisor",
        lambda x: x["next_worker"],
        {
            "linguist": "linguist",
            "context_analyst": "context_analyst",
            "evaluator": "evaluator",
            "tutor": "tutor",
            "FINISH": END
        }
    )
    
    # 작업자 -> Supervisor 복귀
    for node in ["linguist", "context_analyst", "evaluator", "tutor"]:
        workflow.add_edge(node, "supervisor")
        
    return workflow.compile()