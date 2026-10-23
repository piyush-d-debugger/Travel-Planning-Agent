from google.adk.agents import LlmAgent
from .prompt import AGENT_INSTRUCTIONS
from ...tools.activities import search_activities
from ...tools.callback import handle_quota_error

activities_agent = LlmAgent(
    name="activities_agent",
    model="gemini-3.6-flash",
    mode = "single_turn",
    description=(
        "Activities Search Agent"
    ),
    instruction=AGENT_INSTRUCTIONS,
    tools=[search_activities],
    output_key="activity_options",
    on_model_error_callback=handle_quota_error
)