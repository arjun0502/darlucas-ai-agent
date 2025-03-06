import os
import discord
import logging
import aiohttp

from discord.ext import commands
from dotenv import load_dotenv
from agent import MistralAgent
from agent import OpenAIAgent

PREFIX = "!"

# Setup logging
logger = logging.getLogger("discord")

# Load the environment variables
load_dotenv()

# Create the bot with all intents
# The message content and members intent must be enabled in the Discord Developer Portal for the bot to work.
intents = discord.Intents.all()
bot = commands.Bot(command_prefix=PREFIX, intents=intents)

# Import the Mistral agent from the agent.py file
agent = MistralAgent()


# Import the OpenAI agent from the updated agent.py file
agent_openai = OpenAIAgent()


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
    agent_openai.add_to_history(message)
    logger.info(f"Added message from {message.author} to history: {message.content}")


# Commands
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
        image_url, meme_concept = await agent_openai.generate_meme(ctx.channel.id)
        
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

# New command to have the bot react to the memes        
@bot.command(name="react", help="React to the latest message in the chat. Use optional sentiment type (happy, sad, angry, etc.)")
async def react_to_message(ctx, *args):
    """
    React to the latest message in the current channel.
    Optional argument for sentiment (e.g., happy, sad, angry, surprised).
    Usage: !react [sentiment]
    """
    sentiment = None
    if args:
        sentiment = " ".join(args)  # Join all sentiment descriptors, discord bot ignores command by default
    
    # Let the user know we're working on it
    processing_msg = await ctx.send("Generating a reaction to the latest message... 🤔")
    
    try:
        reaction = await agent_openai.react_to_latest(ctx.channel.id, sentiment)
        
        # Display the reaction
        embed = discord.Embed(title="Reaction to Latest Message", color=discord.Color.green())
        embed.description = reaction
        embed.set_footer(text=f"Requested by {ctx.author.display_name}")
        
        # Send the reaction
        await ctx.send(embed=embed)
        
        # Delete the processing message
        await processing_msg.delete()
        
    except Exception as e:
        logger.error(f"Error generating reaction: {e}")
        await processing_msg.edit(content=f"Sorry, I encountered an error while generating the reaction: {str(e)}")

# Start the bot, connecting it to the gateway
bot.run(token)