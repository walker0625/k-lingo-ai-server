from abc import ABC, abstractmethod
from typing import Dict, Any

class BaseMCPTool(ABC):
    """
    모든 MCP 도구가 상속받아야 하는 추상 기본 클래스입니다.
    이 규격을 따르는 도구는 Service의 수정 없이 언제든 추가될 수 있습니다.
    """

    @abstractmethod
    def get_schema(self) -> Dict[str, Any]:
        """
        LLM에게 제공할 도구의 명세서(JSON Schema)를 반환합니다.
        name, description, parameters가 포함되어야 합니다.
        """
        pass

    @abstractmethod
    def run(self, **kwargs) -> str:
        """
        실제 도구의 로직을 수행하고, 그 결과를 문자열로 반환합니다.
        """
        pass