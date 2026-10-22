# services/agent_manager.py

from core.agent import HiraAgent
from core.agent_tools import (
    get_time,
    get_date,
    get_pc_health,
    open_website,
    search_google,
)


def create_hira_agent():

    agent = HiraAgent()

    # ---------------------------------
    # INFORMATION TOOLS
    # ---------------------------------

    agent.register_tool(
        name="get_time",
        description="Get the current local time.",
        function=get_time,
    )

    agent.register_tool(
        name="get_date",
        description="Get today's date.",
        function=get_date,
    )

    agent.register_tool(
        name="get_pc_health",
        description=(
            "Get CPU, RAM, disk and battery "
            "usage of the computer."
        ),
        function=get_pc_health,
    )

    # ---------------------------------
    # BROWSER TOOLS
    # ---------------------------------

    agent.register_tool(
        name="open_website",
        description=(
            "Open a website in the user's browser. "
            "Arguments: url"
        ),
        function=open_website,
    )

    agent.register_tool(
        name="search_google",
        description=(
            "Search Google for information. "
            "Arguments: query"
        ),
        function=search_google,
    )

    return agent