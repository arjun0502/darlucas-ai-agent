import os
import json
import random
import logging
import aiohttp
import urllib.parse
import discord
from typing import List, Dict, Optional, Union, Tuple

# Setup logging
logger = logging.getLogger(__name__)

# API configuration
HUMOR_API_BASE = "https://api.humorapi.com/memes/search"
HUMOR_API_KEY = os.getenv("HUMOR_API_KEY")

async def _make_request(url: str):
    """
    Make a request to the Humor API.
    
    Args:
        url: The URL to make the request to
        
    Returns:
        The JSON response from the API, or None if there was an error
    """
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    error_text = await response.text()
                    logger.error(f"Humor API error: {response.status} - {error_text}")
                    return None
    except Exception as e:
        logger.error(f"Error making request to Humor API: {str(e)}")
        return None

async def search_meme(query: str) -> str:
    """
    Search for memes using the Humor API based on user query.
    Returns a Discord embed with a randomly selected meme or an error message.
    
    Args:
        query: The search query/keywords from the user
        
    Returns:
        A Discord embed with the meme or an error message string
    """
    logger.info(f"Searching for memes based on chat history with query: {query}")
    
    # Clean and prepare the query
    # Split the query into keywords
    keywords = [k.strip() for k in query.split() if k.strip()]
    
    if not keywords:
        return "No relevant memes found."
    
    # Prepare the API URL with parameters
    params = {
        "keywords": ",".join(keywords),
        "keywords-in-image": "false",  # Default to searching in meme text
        "media-type": "image",         # Only return images
        "number": 10,
        "min-rating": 5,               # Only higher-rated memes
        "exclude-tags": "nsfw,dark,racist,sexist,homophobic,transphobic,ableist,ageist,misogynistic,misandric,fatphobic,gay,lgbtq",  # Explicitly exclude problematic content
        "api-key": HUMOR_API_KEY
    }
    
    # Build the URL with parameters
    query_string = "&".join([f"{k}={urllib.parse.quote(str(v))}" for k, v in params.items()])
    url = f"{HUMOR_API_BASE}?{query_string}"
    
    # Make the API request
    data = await _make_request(url)
    
    if data is None:
        return None
    
    # Check if we got any memes
    memes = data.get("memes", [])
    if not memes:
        return None
    
    # Randomly select one meme from the results
    selected_meme = random.choice(memes)
    
    # Create a simple embed with just the image
    embed = discord.Embed(color=discord.Color.purple())
    
    # Add the meme as the main image without any title or description
    embed.set_image(url=selected_meme["url"])
    
    return embed