# ./server/core/agents/telstra/telstra_assist.py
import logging
from typing import Any, List, Dict # Added Dict for callback type hints if used

from google.adk import Agent
from google.adk.tools import BaseTool
# from google.adk.agents.callback_context import CallbackContext # If complex callbacks needed
# from google.adk.tools.tool_context import ToolContext # If complex callbacks needed

from config.config import MODEL
from .prompts import TelstraPrompts # Will import TelstraPrompts from prompts_R3.py
# Assuming session_utils is in parent directory, adjust if necessary
# from ...session_utils import SessionUtils # Example if session_utils is in a parent 'core' directory

# Import all the tools defined for Telstar
from .tools import ( # Will import tools from tools_R3.py
    greeting,
    get_current_datetime_tool,
    custom_web_search,
    web_content_summarizer,
    search_live_telstra_catalog, # Uses the local JSON search implementation
    request_visual_input,
    affirmative,
    update_crm
)

logger = logging.getLogger(__name__)

# --- Callbacks (Optional - Add logic if needed, ensure SessionUtils is correctly imported if used) ---
# def logic_check_telstra(tool: BaseTool, args: Dict[str, Any], tool_context: ToolContext):
#     # SessionUtils.log_before_tool() # Ensure SessionUtils is available
#     logger.debug(f"Telstar Agent: Executing logic_check for tool: {tool.name} with args: {args}")
#     return None

# def after_tool_routing_telstra(tool: BaseTool, args: Dict[str, Any], tool_context: ToolContext, tool_response: Any):
#     # SessionUtils.log_after_tool() # Ensure SessionUtils is available
#     logger.debug(f"Telstar Agent: Executing after_tool_routing for tool: {tool.name}. Output: {tool_response}")
#     return None
# --- End Callbacks ---

def create_telstra_agent(
        model_name: str = MODEL, # Use the global MODEL config
        name: str = "telstra_android_assistant",
        global_instructions: str = TelstraPrompts.GLOBAL_PROMPT,
        instruction: str = TelstraPrompts.TELSTRA_ASSIST_MAIN,
        tools_list: List[BaseTool] = None, # Allow overriding tools for testing
        sub_agents_list: List[Agent] = None
        ) -> Agent:
    """Factory method to create a configured Telstra Agent instance."""

    default_tools = [
            greeting,
            get_current_datetime_tool,
            custom_web_search,
            web_content_summarizer,
            search_live_telstra_catalog, # Now uses the local JSON-backed implementation
            request_visual_input,
            affirmative,
            update_crm
    ]
    
    default_sub_agents = [] # No default sub-agents for Telstar in this design

    # Use provided lists or defaults
    final_tools = tools_list if tools_list is not None else default_tools
    final_sub_agents = sub_agents_list if sub_agents_list is not None else default_sub_agents

    # Deduplication logic if SessionUtils was intended for it (currently commented out in R2)
    # from ...session_utils import SessionUtils # Make sure this path is correct
    # final_tools = SessionUtils.dedupe_lists(default_tools, tools_list or [])
    # final_sub_agents = SessionUtils.dedupe_lists(default_sub_agents, sub_agents_list or [])


    logger.info(f"Creating Telstra agent '{name}' with {len(final_tools)} tools using model '{model_name}'.")
    logger.info(f"Catalog search tool 'search_live_telstra_catalog' is configured to use local JSON data.")

    agent = Agent(
        model=model_name, 
        name=name,
        global_instruction=global_instructions,
        instruction=instruction,
        tools=final_tools,
        sub_agents=final_sub_agents,
    )

    # Assign callbacks if defined and needed (ensure SessionUtils is correctly imported if used)
    # agent.before_tool_callback = logic_check_telstra
    # agent.after_tool_callback = after_tool_routing_telstra
    # agent.before_model_callback = SessionUtils.log_before_model # Ensure SessionUtils is available
    # agent.after_model_callback = SessionUtils.log_after_model  # Ensure SessionUtils is available

    return agent