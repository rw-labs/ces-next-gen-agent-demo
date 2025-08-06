import logging
from typing import Any, Dict, List

# from google.adk.tools.function_tool import FunctionTool # May not be needed if no complex callbacks
# from google.adk.models.llm_response import LlmResponse
# from google.adk.models.llm_request import LlmRequest
# from google.adk.agents.invocation_context import InvocationContext
from config.config import MODEL
from google.adk import Agent
from google.adk.tools import BaseTool
from google.adk.tools.agent_tool import AgentTool
from google.adk.tools.tool_context import ToolContext

from ...session_utils import SessionUtils
from .prompts import DysonPrompts
from .tools import (
    schedule_appointment,
    send_email,
    show_hair_dryer_models,
    show_youtube_video,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(filename)s:%(lineno)d] - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def logic_check(tool: BaseTool, args: Dict[str, Any], tool_context: ToolContext):
    """Perform checks before executing a tool."""
    SessionUtils.log_before_tool()
    logger.info(f"Executing logic_check for tool: {tool.name} with args: {args}")

    # Add other checks if necessary
    return None


def after_tool_routing(
    tool: BaseTool, args: Dict[str, Any], tool_context: ToolContext, tool_response: Any
):
    """Perform actions after a tool executes."""
    SessionUtils.log_after_tool()
    logger.info(
        f"Executing after_tool_routing for tool: {tool.name}. Output: {tool_response}"
    )
    # Example: Log CRM updates
    if tool.name == "update_crm":
        logger.info(
            f"CRM update attempted for customer {args.get('customer_id')}. Result: {tool_response}"
        )
    return None


def before_agent_callback(callback_context):
    print(
        f"Before Agent Callback: Agent {callback_context._invocation_context.agent.name}"
    )
    return None


def after_agent_callback(callback_context):
    print(
        f"After Agent Callback: Agent {callback_context._invocation_context.agent.name}"
    )
    return None


# --- End Callbacks ---


def get_discount_code() -> str:
    """Generate a random 6-digit alphanumeric discount code."""
    import random
    import string

    # Generate random alphanumeric characters
    characters = string.ascii_uppercase + string.digits
    code = "".join(random.choice(characters) for _ in range(6))

    return code


discount_agent = Agent(
    model="gemini-2.0-flash",
    name="discount_agent",
    instruction="""You are a discount agent that return a special discount code where a customer can use in a showroom. The discount code is retrieve using function get_discount_code.""",
    description="""A test agent that return a special discount code.""",
    tools=[get_discount_code],
    disallow_transfer_to_parent=True,
    disallow_transfer_to_peers=True,
)


def create_dyson_agent(
    model: Any = MODEL,
    name: str = "dyson_assist_agent",
    global_instructions: str = DysonPrompts.GLOBAL_PROMPT,
    instruction: str = DysonPrompts.DYSON_ASSIST_MAIN,
    tools: List[BaseTool] = [],
    sub_agents: List[Agent] = [],
) -> Agent:
    """Factory method to create a configured Dyson Agent instance."""

    default_tools = [
        schedule_appointment,
        show_hair_dryer_models,
        show_youtube_video,
        send_email,
        AgentTool(agent=discount_agent),
    ]
    default_sub_agents = []  # No sub-agents defined for this use case yet

    # Deduplicate tools and sub-agents
    final_tools = SessionUtils.dedupe_lists(default_tools, tools)
    final_sub_agents = SessionUtils.dedupe_lists(default_sub_agents, sub_agents)

    logger.info(f"Creating Dyson agent '{name}' with {len(final_tools)} tools.")

    agent = Agent(
        model=model,
        name=name,
        global_instruction=global_instructions,
        instruction=instruction,
        tools=final_tools,
        sub_agents=final_sub_agents,
    )

    # Assign callbacks
    agent.before_tool_callback = logic_check
    agent.after_tool_callback = after_tool_routing
    agent.before_agent_callback = before_agent_callback
    agent.after_agent_callback = after_agent_callback

    # Assign other callbacks if needed (currently None)
    agent.before_agent_callback = None
    agent.after_agent_callback = None
    agent.before_model_callback = None  # SessionUtils.log_before_model
    agent.after_model_callback = None  # SessionUtils.log_after_model

    return agent
