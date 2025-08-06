import logging
from typing import List

from google.adk import Agent
from google.adk.tools import BaseTool

from config.config import MODEL
from .prompts import TallyPrompts
from google.genai import types

from .tools import (
    update_crm,
    custom_web_search,
    web_content_summarizer,
    get_customer_energy_usage,
    request_visual_input,
    search_energy_efficient_fridges,
    get_installation_info,
    book_appointment,
)

logger = logging.getLogger(__name__)

def create_tally_agent(
        model_name: str = MODEL,
        name: str = "tally_assistant",
        global_instructions: str = TallyPrompts.GLOBAL_PROMPT,
        instruction: str = TallyPrompts.TALLY_ASSIST_MAIN,
        tools_list: List[BaseTool] = None,
        sub_agents_list: List[Agent] = None
        ) -> Agent:
    """Factory method to create a configured Tally Agent instance."""

    default_tools = [
        #affirmative,
        update_crm,
        #greeting,
        #get_current_datetime_tool,
        custom_web_search,
        web_content_summarizer,
        get_customer_energy_usage,
        request_visual_input,
        search_energy_efficient_fridges,
        get_installation_info,
        book_appointment,
    ]
    
    default_sub_agents = []

    final_tools = tools_list if tools_list is not None else default_tools
    final_sub_agents = sub_agents_list if sub_agents_list is not None else default_sub_agents

    logger.info(f"Creating Tally agent '{name}' with {len(final_tools)} tools using model '{model_name}'.")

    agent = Agent(
        model=model_name, 
        name=name,
        global_instruction=global_instructions,
        instruction=instruction,
        tools=final_tools,
        sub_agents=final_sub_agents,
        generate_content_config=types.GenerateContentConfig(
            temperature=0.5,
        )
    )

    return agent