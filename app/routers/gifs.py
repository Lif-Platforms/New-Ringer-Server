from fastapi import (
    APIRouter,
    HTTPException,
)
import requests
from urllib.parse import quote
import app.config as config

router = APIRouter()

@router.get("/v1/search")
async def search_gifs(search: str = None):
    # Check if search query is provided
    if not search:
        raise HTTPException(status_code=400, detail="No search query provided.")
    
    # Salinize the search query to prevent issues with special characters
    sanitized_search = quote(search)

    # Load Giphy API key from config
    giphy_api_key = config.get_config('giphy-api-key')

    url = f"https://api.giphy.com/v1/gifs/search?api_key={giphy_api_key}&q={sanitized_search}&limit=20"
    response = requests.get(url, timeout=20)

    return response.json()
        