"""Agent factory for creating agent instances."""
from typing import Dict, Type
from app.agents.base_agent import BaseAgent
from app.agents.mock_agent import MockAgent


# Agent registry
_AGENT_REGISTRY: Dict[str, Type[BaseAgent]] = {
    "mock_agent": MockAgent,
    # Add more agents here as they are implemented
}


def create_agent(agent_type: str) -> BaseAgent:
    """
    Create an agent instance based on agent_type.
    
    Args:
        agent_type: Type of agent to create
        
    Returns:
        Agent instance
        
    Raises:
        ValueError: If agent_type is not registered
    """
    agent_class = _AGENT_REGISTRY.get(agent_type)
    
    if not agent_class:
        raise ValueError(
            f"Unknown agent type: {agent_type}. "
            f"Available types: {list(_AGENT_REGISTRY.keys())}"
        )
    
    return agent_class()


def register_agent(agent_type: str, agent_class: Type[BaseAgent]) -> None:
    """
    Register a new agent type.
    
    Args:
        agent_type: Type identifier for the agent
        agent_class: Agent class to register
    """
    _AGENT_REGISTRY[agent_type] = agent_class


def get_available_agents() -> list[str]:
    """Get list of available agent types."""
    return list(_AGENT_REGISTRY.keys())

