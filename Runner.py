import argparse
import asyncio
import time
from pathlib import Path
 
from dotenv import load_dotenv
 
# Load travel_agent/.env BEFORE importing the agent, as 'adk web' does for you.
load_dotenv(Path(__file__).parent / "travel_agent" / ".env")

from agent import root_agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types



APP_NAME = "travel_agent"
USER_ID = "local_user"
 
# Text from these authors is meant for the user (notes, refusals, the itinerary).
# Everything else (the router's JSON, the specialists' replies) is internal.
USER_FACING = {"travel_planning_workflow", "itinerary_builder"}
 
# A state key appearing means a stage finished. Same idea the web UIs use for their progress list.
PROGRESS = {
    "router_decision": "Understood your request",
    "train_options": "Trains searched",
    "hotel_options": "Hotels searched",
    "activity_options": "Activities searched",
    "final_itinerary": "Itinerary built",
}
 
 
def build_runner() -> tuple[Runner, InMemorySessionService]:
    """Create the session service and the runner that uses it."""
    session_service = InMemorySessionService()
    runner = Runner(
        app_name=APP_NAME,
        node=root_agent,                 # root_agent is a Workflow (a graph), so it goes in node=, not agent=
        session_service=session_service,
    )
    return runner, session_service
 
 
def event_text(event) -> str:
    if not event.content or not event.content.parts:
        return ""
    return "".join(part.text for part in event.content.parts if part.text)
 
 
async def plan_trip(runner: Runner, session_service: InMemorySessionService, question: str,
                    verbose: bool = False, show_state: bool = False) -> None:
    # One new session per request: the workflow is single-turn, so nothing carries over.
    session = await session_service.create_session(app_name=APP_NAME, user_id=USER_ID)
    message = types.Content(role="user", parts=[types.Part(text=question)])
 
    started = time.perf_counter()
    try:
        # run_async yields one event for every step of the workflow, as it happens.
        async for event in runner.run_async(user_id=USER_ID, session_id=session.id, new_message=message):
            elapsed = time.perf_counter() - started
 
            if verbose:
                node = event.node_info.path if getattr(event, "node_info", None) else "-"
                print(f"  [{elapsed:5.1f}s] {event.author:<26} {node}")
 
            for key in event.actions.state_delta:
                if key in PROGRESS:
                    print(f"  [{elapsed:5.1f}s] {PROGRESS[key]}")
 
            text = event_text(event)
            if text and event.author in USER_FACING:
                print(f"\n{text}\n")
    except Exception as exc:  # network, quota, bad credentials...
        print(f"\nRun failed: {type(exc).__name__}: {exc}\n")
        return
 
    if show_state:
        final = await session_service.get_session(app_name=APP_NAME, user_id=USER_ID, session_id=session.id)
        print("Session state at the end:")
        for key, value in final.state.items():
            print(f"  {key:<18} {len(str(value)):>6} characters")
 
 
async def main() -> None:
    parser = argparse.ArgumentParser(description="Run the travel workflow locally.")
    parser.add_argument("question", nargs="?", help="Your travel request (omit for interactive mode)")
    parser.add_argument("--verbose", action="store_true", help="Print every workflow event")
    parser.add_argument("--show-state", action="store_true", help="Print the session state at the end")
    args = parser.parse_args()
 
    runner, session_service = build_runner()
 
    if args.question:
        await plan_trip(runner, session_service, args.question, args.verbose, args.show_state)
    else:
        print("Travel planner. Type a request, or press Enter on an empty line to quit.")
        while True:
            question = input("\nYou> ").strip()
            if not question:
                break
            await plan_trip(runner, session_service, question, args.verbose, args.show_state)
 
    sessions = await session_service.list_sessions(app_name=APP_NAME, user_id=USER_ID)
    print(f"Sessions held in memory by this program: {len(sessions.sessions)}")
    await runner.close()
 
 
if __name__ == "__main__":
    asyncio.run(main())


