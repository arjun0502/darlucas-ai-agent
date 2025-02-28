import os
import discord
import logging
import aiohttp

from discord.ext import commands
from dotenv import load_dotenv
# Import our new OpenAIAgent instead of MistralAgent
from agent_generate import OpenAIAgent

PREFIX = "!"

# Setup logging
logger = logging.getLogger("discord")
logging.basicConfig(level=logging.INFO)

# Load the environment variables
load_dotenv()

# Create the bot with all intents
# The message content and members intent must be enabled in the Discord Developer Portal for the bot to work.
intents = discord.Intents.all()
bot = commands.Bot(command_prefix=PREFIX, intents=intents)

# Import the OpenAI agent from the updated agent.py file
agent = OpenAIAgent()


# Get the token from the environment variables
token = os.getenv("DISCORD_TOKEN")


@bot.event
async def on_ready():
    """
    Called when the client is done preparing the data received from Discord.
    Prints message on terminal when bot successfully connects to discord.

    https://discordpy.readthedocs.io/en/latest/api.html#discord.on_ready
    """
    logger.info(f"{bot.user} has connected to Discord!")


@bot.event
async def on_message(message: discord.Message):
    """
    Called when a message is sent in any channel the bot can see.

    https://discordpy.readthedocs.io/en/latest/api.html#discord.on_message
    """
    # Don't delete this line! It's necessary for the bot to process commands.
    await bot.process_commands(message)

    # Ignore messages from self or other bots to prevent infinite loops.
    if message.author.bot or message.content.startswith("!"):
        return

    # Just add message to chat history, but don't respond to every message
    agent.add_to_history(message)
    logger.info(f"Added message from {message.author} to history: {message.content}")


# Commands

# This example command is here to show you how to add commands to the bot.
# Run !ping with any number of arguments to see the command in action.
@bot.command(name="ping", help="Pings the bot.")
async def ping(ctx, *, arg=None):
    if arg is None:
        await ctx.send("Pong!")
    else:
        await ctx.send(f"Pong! Your argument was {arg}")


# New command for generating memes based on chat history
@bot.command(name="generate", help="Generate a meme based on recent chat history.")
async def generate_meme(ctx):
    """
    Generate a meme based on the chat history in the current channel.
    """
    # Let the user know we're working on it
    processing_msg = await ctx.send("Generating a meme based on your conversation... 🧠")
    
    try:
        # Call the agent to generate a meme
        image_url, meme_concept = await agent.generate_meme(ctx.channel.id)
        
        if not image_url:
            await processing_msg.edit(content=f"Couldn't generate a meme: {meme_concept}")
            return
            
        # Create an embed to display the meme with its concept
        embed = discord.Embed(title="Generated Meme", color=discord.Color.blue())
        embed.description = f"**Concept**: {meme_concept}"
        embed.set_image(url=image_url)
        embed.set_footer(text=f"Requested by {ctx.author.display_name}")
        
        # Send the meme
        await ctx.send(embed=embed)
        
        # Delete the processing message
        await processing_msg.delete()
        
    except Exception as e:
        logger.error(f"Error generating meme: {e}")
        await processing_msg.edit(content=f"Sorry, I encountered an error while generating the meme: {str(e)}")


# Start the bot, connecting it to the gateway
bot.run(token)