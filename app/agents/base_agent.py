"""Base Agent class for all agent implementations."""
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
import asyncio


class BaseAgent(ABC):
    """
    Base class for all Agent implementations.
    
    Provides common functionality for:
    - Task execution
    - Input preparation
    - Response parsing
    - Error handling
    """
    
    def __init__(self, agent_type: str):
        """
        Initialize the agent.
        
        Args:
            agent_type: Type identifier for this agent
        """
        self.agent_type = agent_type
    
    async def execute(self, task_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the agent task.
        
        Args:
            task_id: Unique task identifier
            payload: Task payload containing input data
            
        Returns:
            Processing result dictionary
        """
        try:
            # Prepare input
            prepared_input = await self.prepare_input(payload)
            
            # Process the task
            result = await self.process(task_id, prepared_input)
            
            # Parse and return response
            return await self.parse_response(result)
            
        except Exception as e:
            return self.handle_error(task_id, e)
    
    @abstractmethod
    async def prepare_input(self, payload: Dict[str, Any]) -> Any:
        """
        Prepare input data for processing.
        
        Args:
            payload: Raw payload data
            
        Returns:
            Prepared input for processing
        """
        pass
    
    @abstractmethod
    async def process(self, task_id: str, prepared_input: Any) -> Any:
        """
        Process the task with prepared input.
        
        Args:
            task_id: Task identifier
            prepared_input: Prepared input data
            
        Returns:
            Raw processing result
        """
        pass
    
    @abstractmethod
    async def parse_response(self, raw_result: Any) -> Dict[str, Any]:
        """
        Parse raw result into standardized response format.
        
        Args:
            raw_result: Raw processing result
            
        Returns:
            Standardized response dictionary
        """
        pass
    
    def handle_error(self, task_id: str, error: Exception) -> Dict[str, Any]:
        """
        Handle processing errors.
        
        Args:
            task_id: Task identifier
            error: Exception that occurred
            
        Returns:
            Error response dictionary
        """
        return {
            "success": False,
            "error": str(error),
            "task_id": task_id,
            "agent_type": self.agent_type
        }
