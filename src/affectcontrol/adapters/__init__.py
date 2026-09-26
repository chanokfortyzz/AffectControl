"""Experimental, dependency-optional integration helpers.

These are small bridges, not official framework integrations and not authorization layers.
"""
from .langgraph import LangGraphControlNode
from .openai_agents import OpenAIAgentsContext, apply_to_openai_context
from .autogen import AutoGenControlBridge
from .crewai import CrewAIFlowControlBridge

__all__=["LangGraphControlNode","OpenAIAgentsContext","apply_to_openai_context","AutoGenControlBridge","CrewAIFlowControlBridge"]
