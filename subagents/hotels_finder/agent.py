from google.adk.agents import LlmAgent
from .prompt import AGENT_INSTRUCTIONS
from ...tools.hotels import search_hotels
from ...tools.callback import handle_quota_error

hotels_agent = LlmAgent(
    name="hotels_agent",
    model="gemini-3.6-flash",
    mode = "single_turn",
    description=(
        "Hotel Search Agent"
    ),
    instruction=AGENT_INSTRUCTIONS,
    tools=[search_hotels],
    output_key="hotel_options",
   on_model_error_callback=handle_quota_error
)