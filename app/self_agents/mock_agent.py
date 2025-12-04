"""Mock Agent implementation for testing."""
import asyncio
from typing import Any, Dict
from app.self_agents.base_agent import BaseAgent
from app.models.task import TaskResult


class MockAgent(BaseAgent):
    """Mock Agent for testing purposes."""
    
    def __init__(self):
        super().__init__(agent_type="mock_agent")
    
    async def prepare_input(self, payload: Dict[str, Any]) -> str:
        """Extract content from payload."""
        # Handle multiple possible content field locations
        content = (
            payload.get("content") or              # Direct content field
            payload.get("payload", {}).get("content") or  # Nested content in payload
            payload.get("payload") or              # Raw payload string
            str(payload)                           # Fallback to string representation
        )
        return content
    
    async def process(self, task_id: str, prepared_input: str) -> TaskResult:
        """
        Simulate AI processing with mock logic.
        
        Args:
            task_id: Task identifier
            prepared_input: Content to process
            
        Returns:
            Mock processing result
        """
        # Simulate processing delay
        await asyncio.sleep(3)
        
        # Generate mock result
        result = TaskResult(
            tags=["数码", "降价敏感"],
            score=95,
            reason=f"用户关注了内容: {prepared_input}"
        )
        
        return result
    
    async def parse_response(self, raw_result: TaskResult) -> Dict[str, Any]:
        """Parse TaskResult into dictionary."""
        return {
            "success": True,
            "data": raw_result.model_dump(),
            "agent_type": self.agent_type
        }
