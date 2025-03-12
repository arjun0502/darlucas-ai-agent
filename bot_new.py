import os
import discord
import logging
import platform

from discord.ext import commands
from dotenv import load_dotenv
from agent_new import MemeAgent
from tools.leaderboard import leaderboard, generate_leaderboard_embed, process_command, generate_paginated_leaderboard, LeaderboardView

intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True  # Enable reactions intent for handling upvotes/downvotes
intents.members = True    # Enable members intent for user information


logger = logging.getLogger("discord")


PREFIX = "!"
CUSTOM_STATUS = "the forecasts"
class DiscordBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix=commands.when_mentioned_or(PREFIX), intents=intents
        )

        self.logger = logger
        self.meme_agent = MemeAgent()
        self.chat_history = []
        self.active_leaderboards = {}  # Centralized storage for active leaderboard views
        
        self.add_commands()

    async def on_ready(self):
        self.logger.info("-------------------")
        self.logger.info(f"Logged in as {self.user}")
        self.logger.info(f"Discord.py API version: {discord.__version__}")
        self.logger.info(f"Python version: {platform.python_version()}")
        self.logger.info(
            f"Running on: {platform.system()} {platform.release()} ({os.name})"
        )
        self.logger.info("-------------------")

        # Set the bot's custom status to "Watching the forecasts"
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching, name=CUSTOM_STATUS
            )
        )

    async def on_message(self, message: discord.Message):
        await self.process_commands(message)

        # Ignore messages from self or other bots.
        if (
            message.author == self.user
            or message.author.bot
            or message.content.startswith("!")
        ):
            return

        self.logger.info(f"Message from {message.author}: {message.content}")

        # Add message to chat history
        self.meme_agent.add_to_chat_history(message)
        self.meme_agent.add_score_to_user(message.author.name)
        
        # Run the meme agent whenever the bot receives a message.
        await self.meme_agent.run(message)

    async def on_reaction_add(self, reaction, user):
        """Event handler for when a reaction is added to a message"""
        # Ignore reactions from the bot itself
        if user == self.user:
            return
        
        # Pass the reaction to the meme agent for handling
        await self.meme_agent.handle_reaction(reaction, user)

    async def on_reaction_remove(self, reaction, user):
        """Event handler for when a reaction is removed from a message"""
        # Ignore reactions from the bot itself
        if user == self.user:
            return
        
        # Pass the reaction to the meme agent for handling
        await self.meme_agent.handle_reaction_remove(reaction, user)

    async def handle_leaderboard_buttons(self, interaction: discord.Interaction):
        """Handle button interactions for the leaderboard"""
        message_id = str(interaction.message.id)
        self.logger.info(f"Button interaction received for message {message_id}")
        
        # Check if we have this message ID in our tracking
        if message_id not in self.active_leaderboards:
            # If not found, inform the user
            await interaction.response.send_message("This leaderboard session has expired. Please use !leaderboard again.", ephemeral=True)
            return
        
        view = self.active_leaderboards[message_id]
        
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
            self.logger.info(f"Successfully updated leaderboard to page {view.current_page + 1}")
        except Exception as e:
            self.logger.error(f"Error editing message: {e}")
            await interaction.response.send_message("Something went wrong. Please try !leaderboard again.", ephemeral=True)

    async def on_interaction(self, interaction: discord.Interaction):
        """Handle interaction events"""
        if interaction.type == discord.InteractionType.component:
            if interaction.data.get('custom_id') in ['prev', 'next']:
                await self.handle_leaderboard_buttons(interaction)

    def add_commands(self):
        @self.command(name="leaderboard")
        async def _leaderboard(ctx):
            """Display the meme leaderboard with pagination accessible to all users"""
            embed, view = await generate_paginated_leaderboard()
            
            if view:
                # Send message and get the message object
                message = await ctx.send(embed=embed, view=view)
                
                # Now update the view with the real message ID and store it
                message_id = str(message.id)
                view.message_id = message_id
                self.active_leaderboards[message_id] = view
                self.logger.info(f"Created new leaderboard with ID {message_id}")
            else:
                await ctx.send(embed=embed)
                
        @self.command(name="mystats")
        async def _mystats(ctx):
            """Display your personal meme stats"""
            user_id = str(ctx.author.id)
            embed = await process_command("mystats", user_id)
            await ctx.send(embed=embed)


if __name__ == "__main__":
    load_dotenv()
    token = os.getenv("DISCORD_TOKEN")

    bot = DiscordBot()
    bot.run(token)