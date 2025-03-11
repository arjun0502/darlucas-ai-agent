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

async def search_memes(query: str) -> str:
    """
    Search for memes using the Humor API based on user query.
    Returns a Discord embed with a randomly selected meme or an error message.
    
    Args:
        query: The search query/keywords from the user
        number: Number of memes to fetch (default: 10)
        exclude_nsfw: Whether to exclude NSFW content (default: True)
        
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
        return "Error fetching memes from Humor API. Please try again later."
    
    # Check if we got any memes
    memes = data.get("memes", [])
    if not memes:
        return f"No memes found for '{query}'"
    
    # Randomly select one meme from the results
    selected_meme = random.choice(memes)
    
    # Get the description (or use a default if not available)
    description = selected_meme.get("description", "No description available")
    
    # Create an embed to display the meme
    embed = discord.Embed(
        title=f"Random Meme for '{query}'", 
        description=f"**{description}**\n\nFound {data.get('available', 0)} memes. Showing a random one:", 
        color=discord.Color.purple()
    )
    
    # Add the meme as the main image
    embed.set_image(url=selected_meme["url"])
    
    # Add additional meme details if available
    if selected_meme.get("width") and selected_meme.get("height"):
        embed.add_field(
            name="Dimensions", 
            value=f"{selected_meme['width']}×{selected_meme['height']}", 
            inline=True
        )
    
    if selected_meme.get("type"):
        embed.add_field(
            name="Type", 
            value=selected_meme["type"].replace("image/", "") if "image/" in selected_meme["type"] else selected_meme["type"], 
            inline=True
        )
    
    # Add footer with search info
    embed.set_footer(text=f"Search: {query} • Type !search {query} again for a different meme")
    
    return embed