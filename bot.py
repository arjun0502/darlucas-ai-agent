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

# Import the Mistral and OpenAI agent from the agent.py file
agent_mistral = MistralAgent()
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
    
    # Add message to chat history
    agent_mistral.add_to_chat_history(message)
    logger.info(f"Added message from {message.author} to history: {message.content}")

    try:
        spontaneous_meme_decision, spontaneous_meme_reason = await agent_mistral.decide_spontaneous_meme()
        logger.info(f"Spontaneous meme decision: {spontaneous_meme_decision}, reason: {spontaneous_meme_reason}")

        if spontaneous_meme_decision:
            await generate_spontaneous_meme(message)
    except Exception as e:
        logger.error(f"Error deciding spontaneous meme: {e}")

        
# Commands
# New command for generating memes based on chat history
@bot.command(name="generate", help="Generate a meme based on recent chat history.")
async def generate_meme(ctx):
    """
    Generate a meme based on the chat history in the current channel.
    """
    # Let the user know we're working on it
    processing_msg = await ctx.send("Generating a meme based on your conversation....")
    
    try:
        # Call Mistral agent to generate meme concept (text)
        meme_concept = await agent_mistral.generate_meme_concept_from_chat_history()
        # Call OpenAI agent (Dall-E) to generate meme (image)
        image_url = await agent_openai.generate_meme_from_concept(meme_concept)
        
        if not image_url:
            await processing_msg.edit(content=f"Couldn't generate a meme: {meme_concept}")
            return
            
        # Create an embed to display the meme
        embed = discord.Embed(title="Generated Meme", color=discord.Color.blue())
        embed.set_image(url=image_url)
        embed.set_footer(text=f"Requested by {ctx.author.display_name}")
        
        # Send the meme
        await ctx.send(embed=embed)
        
        # Delete the processing message
        await processing_msg.delete()
        
    except Exception as e:
        logger.error(f"Error generating meme: {e}")
        await processing_msg.edit(content=f"Sorry, I encountered an error while generating the meme: {str(e)}")

# Function for spontaneous meme generation (called from on_message)
async def generate_spontaneous_meme(message):
    """
    Generate a spontaneous meme based on the chat history in the current channel.
    Similar to the command version but works with a message object instead of ctx.
    """
    # Let the user know we're working on it
    processing_msg = await message.channel.send("I've decided this conversation deserves a meme.......")
    
    try:
        # Call Mistral agent to generate meme concept (text)
        meme_concept = await agent_mistral.generate_meme_concept_from_chat_history()
        # Call OpenAI agent (Dall-E) to generate meme (image)
        image_url = await agent_openai.generate_meme_from_concept(meme_concept)
        
        if not image_url:
            await processing_msg.edit(content=f"Couldn't generate a meme: {meme_concept}")
            return
            
        # Create an embed to display the meme
        embed = discord.Embed(title="Spontaneous Meme", color=discord.Color.green())
        embed.set_image(url=image_url)
        embed.set_footer(text=f"Generated spontaneously based on your conversation")
        
        # Send the meme
        await message.channel.send(embed=embed)
        
        # Delete the processing message
        await processing_msg.delete()
        
    except Exception as e:
        logger.error(f"Error generating spontaneous meme: {e}")
        await processing_msg.edit(content=f"Sorry, I encountered an error while generating the meme: {str(e)}")

# Start the bot, connecting it to the gateway
bot.run(token)