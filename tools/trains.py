import os
import logging
import requests
from typing import Optional
from pydantic import BaseModel, Field

class TrainRequest(BaseModel):
    """Request model for Indian Railways train search."""
    origin: str = Field(..., description="IRCTC station code of the departure station (e.g., 'NDLS')")
    destination: str = Field(..., description="IRCTC station code of the arrival station (e.g., 'BCT')")
    travel_date: str = Field(..., description="Travel date in 'YYYY-MM-DD' format")
    class_type: Optional[str] = Field("SL", description="Travel class code")

def search_trains(train_request: TrainRequest):
    """Search Indian trains using the Rail Radar API."""
    

    url = "https://api.railradar.in/v1/legacy/trains/between"
    
    params = {
        "from": train_request.origin.strip().upper(),
        "to": train_request.destination.strip().upper()
    }
    
   
    api_key = os.getenv("RAIL_RADAR_API_KEY")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status() 
        return response.json()
    except requests.exceptions.RequestException as e:
        logging.exception("Error searching trains with Rail Radar: %s", str(e))
        return {"error": str(e)}
