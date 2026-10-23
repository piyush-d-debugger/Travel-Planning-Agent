from google.adk.agents import LlmAgent
from .prompt import AGENT_INSTRUCTIONS
from ...tools.trains import search_trains  
from ...tools.callback import handle_quota_error

trains_agent = LlmAgent(
    name="trains_agent",                  
    model="gemini-3.6-flash",
    mode = "single_turn",
    description="Trains Search Agent",    
    instruction=AGENT_INSTRUCTIONS,
    tools=[search_trains],                 
    output_key="train_options",            
    on_model_error_callback=handle_quota_error
)