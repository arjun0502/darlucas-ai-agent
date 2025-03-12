import discord
import logging
from typing import Optional, Dict, Any, List, Union

from tools.leaderboard import leaderboard

# Set up logging configuration
logger = logging.getLogger(__name__)

async def get_meme_data(meme_number: Optional[int] = None) -> Dict[str, Any]:
    """
    Get the data for a specific meme or the top meme to be judged.
    
    Args:
        meme_number: Optional position in the leaderboard (1-indexed)
        
    Returns:
        Dict with meme data or error information
    """
    # Get top memes
    top_memes = leaderboard.get_top_memes(limit=10)
    
    if not top_memes:
        return {
            "status": "error",
            "message": "No memes in the leaderboard yet"
        }
    
    # Default to judging the top meme if no specific meme is requested
    index = 0 if meme_number is None else meme_number - 1
    
    # Check if the requested index is valid
    if index < 0 or index >= len(top_memes):
        return {
            "status": "error",
            "message": f"Cannot judge meme #{meme_number} because it doesn't exist! There are only {len(top_memes)} memes in the leaderboard."
        }
    
    # Get the meme to judge
    meme = top_memes[index]
    
    # Format the data to be returned
    meme_data = {
        "status": "success",
        "position": index + 1,
        "author": meme.get("author_name", "Unknown"),
        "upvotes": meme.get("upvotes", 0),
        "downvotes": meme.get("downvotes", 0),
        "ratio": meme.get("upvotes", 0) / max(1, meme.get("upvotes", 0) + meme.get("downvotes", 0)),
        "created_at": meme.get("created_at", "Unknown"),
        "embed_data": meme.get("embed_data", {})
    }
    
    return meme_data

async def get_channel_taste_data() -> Dict[str, Any]:
    """
    Get data about the channel's overall taste in memes.
    
    Returns:
        Dict with channel taste data or error information
    """
    # Get top memes
    top_memes = leaderboard.get_top_memes(limit=10)
    
    if not top_memes or len(top_memes) < 3:
        return {
            "status": "error",
            "message": "Not enough memes in the leaderboard to judge channel taste (need at least 3)"
        }
    
    # Analyze overall stats
    total_upvotes = sum(meme.get('upvotes', 0) for meme in top_memes)
    total_downvotes = sum(meme.get('downvotes', 0) for meme in top_memes)
    
    # Check if there's engagement
    if total_upvotes + total_downvotes < 3:
        return {
            "status": "error",
            "message": "Not enough voting activity to judge the channel's taste yet"
        }
    
    # Calculate the average ratio of upvotes to total votes
    ratios = [meme.get('upvotes', 0) / max(1, meme.get('upvotes', 0) + meme.get('downvotes', 0)) for meme in top_memes[:5]]
    avg_ratio = sum(ratios) / len(ratios)
    
    # Get basic info about top 10 memes
    top_5_info = []
    for i, meme in enumerate(top_memes[:10]):
        top_5_info.append({
            "position": i + 1,
            "author": meme.get("author_name", "Unknown"),
            "upvotes": meme.get("upvotes", 0),
            "downvotes": meme.get("downvotes", 0),
            "ratio": meme.get("upvotes", 0) / max(1, meme.get("upvotes", 0) + meme.get("downvotes", 0))
        })
    
    # Format the data to be returned
    channel_data = {
        "status": "success",
        "total_memes": len(top_memes),
        "total_upvotes": total_upvotes,
        "total_downvotes": total_downvotes,
        "average_ratio": avg_ratio,
        "top_memes": top_5_info
    }
    
    return channel_data

async def judge_meme(meme_number: Optional[int] = None) -> discord.Embed:
    """
    Prepare data for the LLM to judge a meme based on its position in the leaderboard.
    If no position is specified, judge the top meme.
    
    Args:
        meme_number: Optional position in the leaderboard (1-indexed)
        
    Returns:
        discord.Embed: The data is provided to the LLM which will generate the judgment text
    """
    # Get data for the meme
    meme_data = await get_meme_data(meme_number)
    
    # Handle errors
    if meme_data.get("status") == "error":
        embed = discord.Embed(
            title="🧐 Meme Judge",
            description=meme_data.get("message", "Error judging meme"),
            color=discord.Color.red()
        )
        return embed
    
    # For successful data retrieval, create a base embed that the LLM will fill with its judgment
    position_str = f"#{meme_data['position']}" if meme_number is not None else "top"
    embed = discord.Embed(
        title=f"🧐 Meme Judge: {position_str} Meme",
        # The LLM will be responsible for filling in the description with its judgment
        description="The LLM will provide its judgment here based on the meme data",
        color=discord.Color.blue()
    )
    
    # Add meme stats
    embed.add_field(
        name="Meme Stats",
        value=f"⬆️ {meme_data['upvotes']} | ⬇️ {meme_data['downvotes']} | Ratio: {meme_data['ratio']:.0%}",
        inline=False
    )
    
    # Add meme creator info
    embed.add_field(
        name="Created by",
        value=meme_data['author'],
        inline=True
    )
    
    # Add image if available
    embed_data = meme_data.get('embed_data', {})
    if 'image_url' in embed_data:
        embed.set_image(url=embed_data['image_url'])
    
    return embed

async def judge_channel_taste() -> discord.Embed:
    """
    Prepare data for the LLM to judge the overall taste of the channel based on the leaderboard.
    
    Returns:
        discord.Embed: The data is provided to the LLM which will generate the judgment text
    """
    # Get data for the channel taste
    channel_data = await get_channel_taste_data()
    
    # Handle errors
    if channel_data.get("status") == "error":
        embed = discord.Embed(
            title="🧐 Channel Taste Judge",
            description=channel_data.get("message", "Error judging channel taste"),
            color=discord.Color.red()
        )
        return embed
    
    # For successful data retrieval, create a base embed that the LLM will fill with its judgment
    embed = discord.Embed(
        title="🧐 Channel Taste Judgment",
        # The LLM will be responsible for filling in the description with its judgment
        description="The LLM will provide its judgment here based on the channel taste data",
        color=discord.Color.blue()
    )
    
    # Add stats
    embed.add_field(
        name="Top 5 Memes Analysis",
        value=f"Average Upvote Ratio: {channel_data['average_ratio']:.0%}\nTotal Upvotes: {channel_data['total_upvotes']}\nTotal Downvotes: {channel_data['total_downvotes']}",
        inline=False
    )
    
    # Add top meme preview if available
    if channel_data['top_memes']:
        top_meme = channel_data['top_memes'][0]
        embed.add_field(
            name="Current #1 Meme",
            value=f"By: {top_meme['author']}\n⬆️ {top_meme['upvotes']} | ⬇️ {top_meme['downvotes']}",
            inline=False
        )
    
    return embed