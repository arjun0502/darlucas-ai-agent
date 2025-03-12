import os
import json
import logging
import discord
from discord.ui import View, Button
from typing import Dict, List, Optional, Union, Any, Tuple
from datetime import datetime

# Setup logging
logger = logging.getLogger(__name__)

# Global dictionary to track active leaderboard pages
active_leaderboards = {}

class LeaderboardView(View):
    def __init__(self, memes: List[Dict], message_id: str):
        super().__init__(timeout=60)  # 60 second timeout
        self.memes = memes
        self.current_page = 0
        self.total_pages = len(memes)
        self.message_id = message_id
        
        # Add navigation 
        self.add_item(Button(label="⬅️ Previous", custom_id="prev", style=discord.ButtonStyle.secondary))
        self.add_item(Button(label="➡️ Next", custom_id="next", style=discord.ButtonStyle.primary))
    
    async def on_timeout(self):
        # Clear buttons when the view times out
        self.clear_items()
        # Remove from active leaderboards
        if self.message_id in active_leaderboards:
            del active_leaderboards[self.message_id]
    
    async def generate_embed(self) -> discord.Embed:
        """Generate an embed for the current page"""
        if not self.memes or self.current_page >= len(self.memes):
            return discord.Embed(
                title="No memes available",
                description="There are no memes to display.",
                color=discord.Color.red()
            )
        
        meme = self.memes[self.current_page]
        medal = "🥇" if self.current_page == 0 else "🥈" if self.current_page == 1 else "🥉" if self.current_page == 2 else f"{self.current_page+1}."
        
        embed = discord.Embed(
            title=f"{medal} Meme Leaderboard Position #{self.current_page + 1}",
            color=discord.Color.gold()
        )
        # Add header title
        embed.set_author(name="🏆 Certified Funny™ Leaderboard 🏆")
    
        
        
        # Add scores
        score = f"⬆️ {meme.get('upvotes', 0)} | ⬇️ {meme.get('downvotes', 0)}"
        embed.add_field(name="Score", value=score, inline=True)
        
        # Add creation date
        created_date = meme.get('created_at', 'Unknown').split('T')[0]
        embed.add_field(name="Created", value=created_date, inline=True)
        
        # Add page counter
        embed.set_footer(text=f"Page {self.current_page + 1}/{self.total_pages} • React with 👍 or 👎 to vote on memes")
        
        # Extract meme content
        embed_data = meme.get('embed_data', {})
        
        # Add caption/title
        meme_title = embed_data.get('title', '')
        if meme_title:
            embed.title = meme_title
            
        # Add description if available
        meme_description = embed_data.get('description', '')
        if meme_description:
            embed.description = meme_description
            
        # Set image if available
        if 'image_url' in embed_data:
            embed.set_image(url=embed_data['image_url'])
            
        return embed

class MemeLeaderboard:
    def __init__(self, db_file="meme_leaderboard.json"):
        self.db_file = db_file
        self.memes = {}  # message_id -> meme data
        self.load_db()
    
    def load_db(self):
        """Load the leaderboard database from file"""
        try:
            if os.path.exists(self.db_file):
                with open(self.db_file, 'r') as f:
                    data = json.load(f)
                    self.memes = data.get('memes', {})
                logger.info(f"Loaded leaderboard data with {len(self.memes)} memes")
            else:
                logger.info(f"No leaderboard file found at {self.db_file}, starting fresh")
                self.memes = {}
                self.save_db()  # Create the file
        except Exception as e:
            logger.error(f"Error loading leaderboard database: {e}")
            self.memes = {}
    
    def save_db(self):
        """Save the leaderboard database to file"""
        try:
            data = {
                'memes': self.memes,
                'last_updated': datetime.now().isoformat()
            }
            with open(self.db_file, 'w') as f:
                json.dump(data, f, indent=2)
            logger.info(f"Saved leaderboard data with {len(self.memes)} memes")
            return True
        except Exception as e:
            logger.error(f"Error saving leaderboard database: {e}")
            return False
    
    def add_meme(self, message_id: str, author_id: str, author_name: str, embed_data: Dict):
        """Add a new meme to the leaderboard"""
        if message_id in self.memes:
            logger.warning(f"Meme with message_id {message_id} already exists, not adding again")
            return False
        
        self.memes[message_id] = {
            'message_id': message_id,
            'author_id': author_id,
            'author_name': author_name,
            'embed_data': embed_data,
            'upvotes': 0,
            'downvotes': 0,
            'created_at': datetime.now().isoformat(),
            'voters': {}  # user_id -> vote (1 for upvote, -1 for downvote)
        }
        
        self.save_db()
        logger.info(f"Added new meme with message_id {message_id} by {author_name}")
        return True
    
    def update_vote(self, message_id: str, user_id: str, is_upvote: bool) -> bool:
        """Update the vote count for a meme"""
        if message_id not in self.memes:
            logger.warning(f"Meme with message_id {message_id} not found, can't update vote")
            return False
        
        meme = self.memes[message_id]
        previous_vote = meme['voters'].get(user_id, 0)
        
        # Remove previous vote if any
        if previous_vote == 1:
            meme['upvotes'] -= 1
        elif previous_vote == -1:
            meme['downvotes'] -= 1
        
        # Add new vote
        if is_upvote:
            meme['upvotes'] += 1
            meme['voters'][user_id] = 1
        else:
            meme['downvotes'] += 1
            meme['voters'][user_id] = -1
        
        self.save_db()
        logger.info(f"Updated vote for meme {message_id}: {'upvote' if is_upvote else 'downvote'} by user {user_id}")
        return True
    
    def remove_vote(self, message_id: str, user_id: str) -> bool:
        """Remove a vote from a meme"""
        if message_id not in self.memes:
            logger.warning(f"Meme with message_id {message_id} not found, can't remove vote")
            return False
        
        meme = self.memes[message_id]
        if user_id not in meme['voters']:
            return False
        
        previous_vote = meme['voters'][user_id]
        if previous_vote == 1:
            meme['upvotes'] -= 1
        elif previous_vote == -1:
            meme['downvotes'] -= 1
        
        del meme['voters'][user_id]
        self.save_db()
        logger.info(f"Removed vote for meme {message_id} by user {user_id}")
        return True
    
    def get_top_memes(self, limit: int = 10, sort_by: str = 'upvotes') -> List[Dict]:
        """Get the top memes sorted by upvotes or net score (upvotes - downvotes)"""
        if sort_by == 'upvotes':
            sorted_memes = sorted(
                self.memes.values(), 
                key=lambda x: x.get('upvotes', 0), 
                reverse=True
            )
        else:  # net score
            sorted_memes = sorted(
                self.memes.values(), 
                key=lambda x: x.get('upvotes', 0) - x.get('downvotes', 0), 
                reverse=True
            )
        
        return sorted_memes[:limit]
    
    def get_user_stats(self, user_id: str) -> Dict:
        """Get statistics for a specific user"""
        stats = {
            'user_id': user_id,
            'total_memes': 0,
            'total_upvotes': 0,
            'total_downvotes': 0,
            'net_score': 0,
            'top_memes': []
        }
        
        user_memes = []
        for meme_id, meme in self.memes.items():
            if meme.get('author_id') == user_id:
                stats['total_memes'] += 1
                stats['total_upvotes'] += meme.get('upvotes', 0)
                stats['total_downvotes'] += meme.get('downvotes', 0)
                user_memes.append(meme)
        
        stats['net_score'] = stats['total_upvotes'] - stats['total_downvotes']
        
        # Get top 3 memes by this user
        user_memes.sort(key=lambda x: x.get('upvotes', 0), reverse=True)
        stats['top_memes'] = user_memes[:3]
        
        return stats

# Global instance that can be imported by other modules
leaderboard = MemeLeaderboard()

async def handle_leaderboard_buttons(interaction: discord.Interaction):
    """Handle button interactions for the leaderboard"""
    message_id = str(interaction.message.id)
    logger.info(f"Button interaction received for message {message_id}")
    
    # Debugging info
    logger.info(f"Active leaderboards: {list(active_leaderboards.keys())}")
    
    # Check if we have this message ID in our tracking
    if message_id not in active_leaderboards:
        # Try to find the view based on the content instead
        try:
            # Create a temporary view to work with
            top_memes = leaderboard.get_top_memes(limit=10)
            temp_view = LeaderboardView(top_memes, message_id)
            
            # Store this message ID in our active leaderboards
            active_leaderboards[message_id] = temp_view
            logger.info(f"Created new tracking for message ID {message_id}")
            
            # Set the view to our newly created one
            view = temp_view
            
            # Handle navigation
            if interaction.data['custom_id'] == 'prev':
                view.current_page = 0  # Start at the beginning
            elif interaction.data['custom_id'] == 'next':
                view.current_page = 1  # Go to second page
        except Exception as e:
            logger.error(f"Error creating new tracking: {e}")
            await interaction.response.send_message("This leaderboard session needs to be reset. Please use !leaderboard again.", ephemeral=True)
            return
    else:
        view = active_leaderboards[message_id]
        
        # Handle navigation
        if interaction.data['custom_id'] == 'prev':
            view.current_page = max(0, view.current_page - 1)
        elif interaction.data['custom_id'] == 'next':
            view.current_page = min(view.total_pages - 1, view.current_page + 1)
    
    # Generate new embed for current page
    embed = await view.generate_embed()
    
    # Update the message
    try:
        await interaction.response.edit_message(embed=embed, view=view)
        logger.info(f"Successfully updated leaderboard to page {view.current_page + 1}")
    except Exception as e:
        logger.error(f"Error editing message: {e}")
        await interaction.response.send_message("Something went wrong. Please try !leaderboard again.", ephemeral=True)

async def generate_paginated_leaderboard() -> Tuple[discord.Embed, Optional[LeaderboardView]]:
    """Generate a paginated leaderboard accessible to all users"""
    top_memes = leaderboard.get_top_memes(limit=10)
    
    if not top_memes:
        embed = discord.Embed(
            title="🏆 Meme Leaderboard 🏆",
            description="No memes yet. Be the first to get on the leaderboard!",
            color=discord.Color.gold()
        )
        return embed, None
    
    # Create a view with temporary ID - we'll update this after sending
    view = LeaderboardView(top_memes, "temp")
    
    # Generate the initial embed
    embed = await view.generate_embed()
    
    return embed, view
# For backward compatibility
async def generate_leaderboard_embed() -> discord.Embed:
    """Generate a non-paginated embed to display the leaderboard (legacy method)"""
    top_memes = leaderboard.get_top_memes(limit=5)
    
    embed = discord.Embed(
        title="🏆 Meme Leaderboard 🏆",
        description="Top 5 memes based on upvotes",
        color=discord.Color.gold()
    )
    
    if not top_memes:
        embed.add_field(name="No memes yet", value="Be the first to get on the leaderboard!", inline=False)
        return embed
    
    for i, meme in enumerate(top_memes):
        medal = "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else f"{i+1}."
        
        score = f"⬆️ {meme.get('upvotes', 0)} | ⬇️ {meme.get('downvotes', 0)}"
        embed.add_field(
            name=f"{medal} {meme.get('author_name', 'Unknown')}",
            value=f"{score}\nCreated: {meme.get('created_at', 'Unknown').split('T')[0]}",
            inline=False
        )
    
    # Add a footer with instructions
    embed.set_footer(text="React with 👍 or 👎 to vote on memes")
    
    return embed

async def process_command(command: str, user_id: str = None) -> Union[discord.Embed, str]:
    """Process leaderboard commands"""
    if command.lower() == "leaderboard":
        # For backward compatibility
        return await generate_leaderboard_embed()
    
    if command.lower() == "mystats" and user_id:
        user_stats = leaderboard.get_user_stats(user_id)
        
        embed = discord.Embed(
            title="🎭 Your Meme Stats 🎭",
            description=f"Stats for <@{user_id}>",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="Summary",
            value=f"Total Memes: {user_stats['total_memes']}\n"
                  f"Total Upvotes: {user_stats['total_upvotes']}\n"
                  f"Total Downvotes: {user_stats['total_downvotes']}\n"
                  f"Net Score: {user_stats['net_score']}",
            inline=False
        )
        
        if user_stats['top_memes']:
            top_meme = user_stats['top_memes'][0]
            embed.add_field(
                name="Your Top Meme",
                value=f"⬆️ {top_meme.get('upvotes', 0)} | ⬇️ {top_meme.get('downvotes', 0)}",
                inline=False
            )
        
        return embed
    
    return "Unknown command"