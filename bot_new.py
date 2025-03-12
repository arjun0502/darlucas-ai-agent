import os
import discord
import logging
import platform

from discord.ext import commands
from dotenv import load_dotenv
from agent_new import MemeAgent
from tools.leaderboard import leaderboard, generate_leaderboard_embed, process_command

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

    def add_commands(self):
        @self.command(name="leaderboard")
        async def _leaderboard(ctx):
            """Display the meme leaderboard"""
            embed = await generate_leaderboard_embed()
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