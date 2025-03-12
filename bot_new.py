import os
import discord
import logging
import platform

from discord.ext import commands
from dotenv import load_dotenv
from agent_new import MemeAgent

intents = discord.Intents.default()

intents.message_content = True

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


if __name__ == "__main__":
    load_dotenv()
    token = os.getenv("DISCORD_TOKEN")

    bot = DiscordBot()
    bot.run(token)