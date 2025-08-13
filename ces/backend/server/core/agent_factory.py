from config.config import DEMO_TYPE

# from core.agents.dyson.context import DysonContext
# from core.agents.dream11.context import Dream11Context
# from core.agents.telstra.context import TelstraContext
# from core.agents.servicesaus.context import ServicesausContext
# from core.agents.teg.context import TegContext
# from core.agents.xtelcom.context import XtelcomContext
# from core.agents.ollie.context import OllieContext
# from core.agents.tally.context import TallyContext
from core.agents.optus_modem.context import OptusModemContext


# from core.agents.dyson.dyson_assist import create_dyson_agent
# from core.agents.dream11.dream11_assist import create_dream11_agent
# from core.agents.telstra.telstra_assist import create_telstra_agent
# from core.agents.servicesaus.servicesaus_assist import create_servicesaus_agent
# from core.agents.teg.teg_assist import create_teg_agent
# from core.agents.xtelcom.xtelcom_assist import create_xtelcom_agent
# from core.agents.ollie.ollie_assist import create_ollie_agent
# from core.agents.tally.tally_assist import create_tally_agent
from core.agents.optus_modem.optus_modem_assist import create_optus_modem_agent

from .logger import logger


def get_agent_config(session_id: str):
    agent_config = {"app_name": None, "root_agent": None, "context": None}

    if DEMO_TYPE == "dyson":
        agent_config["app_name"] = "dyson_retail_assist"
        agent_config["context"] = DysonContext.CUSTOMER_PROFILE
        agent_config["context"]["session_id"] = session_id  # Add session_id to context
        agent_config["root_agent"] = create_dyson_agent()

    # --- Add Dream11 Option ---
    elif DEMO_TYPE == "dream11":
        agent_config["app_name"] = "dream11_ai_assistant"
        agent_config["context"] = Dream11Context.CUSTOMER_PROFILE
        agent_config["context"]["session_id"] = session_id # Add session_id to context
        agent_config["root_agent"] = create_dream11_agent()
    # --- End Dream11 Option ---

    # --- Add services_australia Option ---
    elif DEMO_TYPE == "servicesaus":
        agent_config["app_name"] = "services_australia_ai_assistant"
        agent_config["context"] = ServicesausContext.CUSTOMER_PROFILE
        agent_config["context"]["session_id"] = session_id # Add session_id to context
        agent_config["root_agent"] = create_servicesaus_agent()
    # --- End services_australia Option ---

    # --- Add Telstra Option ---
    elif DEMO_TYPE == "telstra":
        agent_config["app_name"] = "telstra_ai_assistant"
        agent_config["context"] = TelstraContext.CUSTOMER_PROFILE
        agent_config["context"]["session_id"] = session_id # Add session_id to context
        agent_config["root_agent"] = create_telstra_agent()
    # --- End Dream11 Option ---

    # --- Add Teg Option ---
    elif DEMO_TYPE == "teg":
        agent_config["app_name"] = "teg_ai_assistant"
        agent_config["context"] = TegContext.CUSTOMER_PROFILE
        agent_config["context"]["session_id"] = session_id # Add session_id to context
        agent_config["root_agent"] = create_teg_agent()
    # --- End Teg Option ---

    # --- Add Xtelcom Option ---
    elif DEMO_TYPE == "xtelcom":
        agent_config["app_name"] = "xtelcom_ai_assistant"
        agent_config["context"] = XtelcomContext.CUSTOMER_PROFILE
        agent_config["context"]["session_id"] = session_id # Add session_id to context
        agent_config["root_agent"] = create_xtelcom_agent()
    # --- End Xtelcom Option ---

    # --- Add Optus Option ---
    elif DEMO_TYPE == "optus":
        agent_config["app_name"] = "optus_ai_assistant"
        agent_config["context"] = OllieContext.CUSTOMER_PROFILE
        agent_config["context"]["session_id"] = session_id # Add session_id to context
        agent_config["root_agent"] = create_ollie_agent ()
    # --- End Optus Option ---

    # --- Add Tally Option ---
    elif DEMO_TYPE == "tally":
        agent_config["app_name"] = "tally_ai_assistant"
        agent_config["context"] = TallyContext.CUSTOMER_PROFILE
        agent_config["context"]["session_id"] = session_id # Add session_id to context
        agent_config["root_agent"] = create_tally_agent()
    # --- End Tally Option ---

    # --- Add Optus Modem Option ---
    elif DEMO_TYPE == "optus_modem_setup":
        agent_config["app_name"] = "optus_modem_setup"
        agent_config["context"] = OptusModemContext.CUSTOMER_PROFILE
        agent_config["context"]["session_id"] = session_id # Add session_id to context
        agent_config["context"]["video_status"] = "inactive" # Set initial video status
        agent_config["root_agent"] = create_optus_modem_agent ()
    # --- End Optus Modem Option ---

    else:
        raise ValueError(f"Unknown DEMO_TYPE: `{DEMO_TYPE}`")

    logger.info(f"Loading `{DEMO_TYPE}` Agent: {agent_config['app_name']}")

    return agent_config
