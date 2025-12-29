import os
import requests
import logging
from typing import Dict, Any
from .base import BaseMCPTool

logger = logging.getLogger(__name__)

class BraveSearchTool(BaseMCPTool):
    def __init__(self):
        # 환경 변수에서 키를 가져옵니다.
        self.api_key = os.getenv("BRAVE_API_KEY")
        self.endpoint = "https://api.search.brave.com/res/v1/web/search"

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": "web_search",  # [중요] LLM이 기억할 도구 이름
                "description": "최신 뉴스, 날씨, 사실 확인 등 실시간 웹 정보가 필요할 때 사용합니다.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "검색 엔진에 입력할 최적화된 검색어 (예: '서울 날씨', '2024년 AI 트렌드')"
                        }
                    },
                    "required": ["query"],
                },
            }
        }

    def run(self, query: str) -> str:
        if not self.api_key:
            return "Error: Brave API Key가 설정되지 않았습니다."

        try:
            logger.info(f"[MCP Tool] Brave Search 실행: {query}")
            
            headers = {
                "Accept": "application/json",
                "Accept-Encoding": "gzip",
                "X-Subscription-Token": self.api_key
            }
            params = {"q": query, "count": 2} # 결과 2개 요청
            
            response = requests.get(self.endpoint, headers=headers, params=params)
            
            if response.status_code != 200:
                logger.error(f"Brave API Error: {response.status_code}")
                return "Error: 검색 서비스 연결 실패"

            data = response.json()
            results = data.get("web", {}).get("results", [])
            
            if not results:
                return "검색 결과가 없습니다."

            # AI가 읽기 좋게 결과 포맷팅
            formatted_results = []
            for item in results:
                title = item.get('title', 'No Title')
                link = item.get('url', '#')
                desc = item.get('description', '') or item.get('snippet', '')
                formatted_results.append(f"Title: {title}\nURL: {link}\nSummary: {desc}")

            return "\n---\n".join(formatted_results)

        except Exception as e:
            logger.error(f"Search Exception: {e}")
            return f"Error: 검색 중 예외 발생 ({str(e)})"