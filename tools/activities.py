
import logging
from typing import Optional

from pydantic import BaseModel, Field

from .serp_api import run_search


class TripadvisorRequest(BaseModel):
    """Request model for Tripadvisor searches."""

    query: str = Field(
        ...,
        description=(
            "Search query for Tripadvisor, such as a hotel, restaurant, "
            "tourist attraction, or destination (e.g., 'best hotels in Goa')."
        ),
    )

    category: str = Field(
        "all",
        description=(
            "Category to search for: 'hotels', 'restaurants', "
            "'attractions', or 'all'."
        ),
    )

    location: Optional[str] = Field(
        None,
        description="Location or destination to search in (e.g., 'Goa, India').",
    )

    language: str = Field(
        "en",
        description="Language code for search results (e.g., 'en').",
    )

    currency: str = Field(
        "INR",
        description="Currency code for prices (e.g., 'INR', 'USD').",
    )

    max_results: int = Field(
        10,
        ge=1,
        le=50,
        description="Maximum number of results requested.",
    )


def search_activities(request: TripadvisorRequest) -> dict:
    """Search Tripadvisor for hotels, restaurants, or attractions."""

    query = request.query.strip()

    if request.location:
        query = f"{query} in {request.location.strip()}"

    params = {
        "engine": "tripadvisor",
        "q": query,
        "category": request.category.strip().lower(),
        "hl": request.language.strip().lower(),
        "currency": request.currency.strip().upper(),
        "num": request.max_results,
    }

    try:
        search_results = run_search(params)
        return search_results

    except Exception as e:
        logging.exception("Error searching Tripadvisor: %s", str(e))
        return {"error": str(e)}