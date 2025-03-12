import os
import json
import logging
import discord
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any

# Setup logging
logger = logging.getLogger(__name__)

class MemeLeaderboard:
    def __init__(self):
        self.memes_file = "meme_data.json"
        self.meme_data = self.load_meme_data()
    
    def load_meme_data(self) -> Dict:
        """Load meme data from the JSON file, or create a new dictionary if file doesn't exist"""
        try:
            if os.path.exists(self.memes_file):
                with open(self.memes_file, 'r') as f:
                    return json.load(f)
            else:
                return {
                    "memes": {},
                    "last_updated": datetime.now().isoformat()
                }
        except Exception as e:
            logger.error(f"Error loading meme data: {e}")
            return {
                "memes": {},
                "last_updated": datetime.now().isoformat()
            }
    
    def save_meme_data(self) -> None:
        """Save meme data to the JSON file"""
        try:
            self.meme_data["last_updated"] = datetime.now().isoformat()
            with open(self.memes_file, 'w') as f:
                json.dump(self.meme_data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving meme data: {e}")
    
    def track_meme(self, message: discord.Message, embed: discord.Embed, author=None) -> None:
        """
        Track a newly generated meme
        
        Args:
            message: The Discord message containing the meme
            embed: The embed containing the meme data
            author: Optional author override (for when the bot posts on behalf of a user)
        """
        try:
            # Extract the image URL from the embed
            image_url = None
            if embed.image:
                image_url = embed.image.url
            
            # Get field data
            fields = []
            for field in embed.fields:
                fields.append({
                    "name": field.name,
                    "value": field.value,
                    "inline": field.inline
                })
            
            # Use author override if provided, otherwise use message author
            author_id = str(author.id) if author else str(message.author.id)
            author_name = author.name if author else message.author.name
            
            # Store the meme data
            self.meme_data["memes"][str(message.id)] = {
                "message_id": str(message.id),
                "author_id": author_id,
                "author_name": author_name,
                "embed_data": {
                    "title": embed.title,
                    "description": embed.description,
                    "color": embed.color.value if embed.color else None,
                    "fields": fields,
                    "image_url": image_url
                },
                "upvotes": 0,
                "downvotes": 0,
                "created_at": datetime.now().isoformat(),
                "voters": {}
            }
            
            self.save_meme_data()
            logger.info(f"Tracked new meme with ID: {message.id} for author: {author_name}")
        except Exception as e:
            logger.error(f"Error tracking meme: {e}")
    
    async def setup_reactions(self, message: discord.Message) -> None:
        """Add upvote and downvote reactions to a meme message"""
        try:
            await message.add_reaction("👍")  # Thumbs up
            await message.add_reaction("👎")  # Thumbs down
        except Exception as e:
            logger.error(f"Error setting up reactions: {e}")
    
    async def process_reaction(self, reaction: discord.Reaction, user: discord.User, added: bool) -> None:
        """Process an upvote or downvote reaction"""
        try:
            # Ignore bot reactions
            if user.bot:
                return
            
            message_id = str(reaction.message.id)
            user_id = str(user.id)
            
            # Check if this message is being tracked
            if message_id not in self.meme_data["memes"]:
                return
            
            meme = self.meme_data["memes"][message_id]
            emoji = str(reaction.emoji)
            
            # Handle vote addition or removal
            if added:
                # Adding a new vote
                if emoji == "👍":
                    self._add_vote(meme, user_id, 1)
                elif emoji == "👎":
                    self._add_vote(meme, user_id, -1)
            else:
                # Removing a vote
                if emoji == "👍" and user_id in meme["voters"] and meme["voters"][user_id] == 1:
                    self._remove_vote(meme, user_id)
                elif emoji == "👎" and user_id in meme["voters"] and meme["voters"][user_id] == -1:
                    self._remove_vote(meme, user_id)
                    
            # Save the updated data
            self.save_meme_data()
            
        except Exception as e:
            logger.error(f"Error processing reaction: {e}")
    
    def _add_vote(self, meme: Dict, user_id: str, vote_value: int) -> None:
        """Add a vote to a meme (internal helper)"""
        # Remove any existing vote by this user
        self._remove_vote(meme, user_id)
        
        # Add the new vote
        if vote_value == 1:
            meme["upvotes"] += 1
        elif vote_value == -1:
            meme["downvotes"] += 1
            
        # Record who voted and how
        meme["voters"][user_id] = vote_value
    
    def _remove_vote(self, meme: Dict, user_id: str) -> None:
        """Remove a vote from a meme (internal helper)"""
        if user_id in meme["voters"]:
            vote = meme["voters"][user_id]
            if vote == 1:
                meme["upvotes"] = max(0, meme["upvotes"] - 1)
            elif vote == -1:
                meme["downvotes"] = max(0, meme["downvotes"] - 1)
            
            # Remove the voter record
            del meme["voters"][user_id]
    
    def get_top_memes(self, limit: int = 10) -> List[Dict]:
        """Get the top memes sorted by net popularity (upvotes - downvotes)"""
        try:
            # Convert to list and sort
            memes_list = list(self.meme_data["memes"].values())
            sorted_memes = sorted(
                memes_list, 
                key=lambda m: (m["upvotes"] - m["downvotes"], m["upvotes"]), 
                reverse=True
            )
            
            return sorted_memes[:limit]
        except Exception as e:
            logger.error(f"Error getting top memes: {e}")
            return []
    
    def get_user_stats(self, user_id: str) -> Dict:
        """Get statistics for a specific user"""
        try:
            user_id = str(user_id)  # Ensure it's a string
            stats = {
                "memes_created": 0,
                "total_upvotes": 0,
                "total_downvotes": 0,
                "net_popularity": 0,
                "most_popular_meme": None
            }
            
            user_memes = []
            
            # Go through all memes to find user's and calculate stats
            for meme_id, meme in self.meme_data["memes"].items():
                # Count memes created by user
                if meme["author_id"] == user_id:
                    stats["memes_created"] += 1
                    stats["total_upvotes"] += meme["upvotes"]
                    stats["total_downvotes"] += meme["downvotes"]
                    
                    # Add to user's memes for further processing
                    user_memes.append(meme)
            
            # Calculate net popularity
            stats["net_popularity"] = stats["total_upvotes"] - stats["total_downvotes"]
            
            # Find most popular meme if user has any
            if user_memes:
                stats["most_popular_meme"] = max(
                    user_memes,
                    key=lambda m: (m["upvotes"] - m["downvotes"], m["upvotes"])
                )
            
            return stats
        except Exception as e:
            logger.error(f"Error getting user stats: {e}")
            return {
                "memes_created": 0,
                "total_upvotes": 0,
                "total_downvotes": 0,
                "net_popularity": 0,
                "most_popular_meme": None
            }
    
    def reset_all_data(self) -> str:
        """Reset all meme data"""
        try:
            self.meme_data = {
                "memes": {},
                "last_updated": datetime.now().isoformat()
            }
            self.save_meme_data()
            return "All meme leaderboard data has been reset!"
        except Exception as e:
            logger.error(f"Error resetting meme data: {e}")
            return f"Error resetting meme data: {e}"