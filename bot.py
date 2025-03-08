import os
import discord
import logging
import aiohttp
import io
from PIL import Image, ImageDraw, ImageFont
import textwrap

from discord.ext import commands
from dotenv import load_dotenv
from agent import MistralAgent
from agent import OpenAIAgent

PREFIX = "!"

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("discord_bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("discord_bot")

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

# Helper function to add text to images
async def add_text_to_image(image_url, text):
    """
    Downloads an image from URL and adds text below the image with black text and reduced margins
    Returns a file-like object of the modified image
    """
    # Download the image
    async with aiohttp.ClientSession() as session:
        async with session.get(image_url) as response:
            if response.status != 200:
                raise Exception(f"Failed to download image: {response.status}")
            image_data = await response.read()
    
    # Open the image with PIL
    original_image = Image.open(io.BytesIO(image_data))
    
    # Get original image dimensions
    original_width, original_height = original_image.size

    text = text.upper()
    
    # Try to load a good font
    try:
        # Adjust path to where you store the font
        font_path = os.path.join(os.path.dirname(__file__), "Impact.ttf")
        if os.path.exists(font_path):
            font = ImageFont.truetype(font_path, size=int(original_height/14))
        else:
            # Fallback to default font
            font = ImageFont.load_default()
    except:
        # Fallback to default font
        font = ImageFont.load_default()
    
    # Text wrapping
    max_width = int(original_width * 0.95)  # 95% of image width to reduce margins
    chars_per_line = 40  # Allow more characters per line
    
    try:
        # For newer Pillow versions
        avg_char_width = font.getbbox("A")[2]
        chars_per_line = max(1, int(max_width / avg_char_width))
    except:
        # Fallback for older Pillow versions or errors
        pass
    
    wrapped_text = textwrap.fill(text, width=chars_per_line)
    
    # Calculate text height
    try:
        # For newer Pillow versions
        text_bbox = ImageDraw.Draw(Image.new('RGB', (1, 1))).multiline_textbbox((0, 0), wrapped_text, font=font)
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]
    except:
        # Fallback for older Pillow versions
        text_width, text_height = ImageDraw.Draw(Image.new('RGB', (1, 1))).multiline_textsize(wrapped_text, font=font)
    
    # Calculate padding and new image dimensions - use smaller padding
    padding = int(original_height * 0.02)  # Reduced to 2% of image height as padding
    new_height = original_height + text_height + (padding * 2)  # Original + text height + padding above and below
    
    # Create a new larger canvas with extra space below
    new_image = Image.new('RGB', (original_width, new_height), (255, 255, 255))  # White background
    
    # Paste the original image at the top
    new_image.paste(original_image, (0, 0))
    
    # Create a draw object for the new image
    draw = ImageDraw.Draw(new_image)
    
    # Calculate position to center text in the new space below the image
    position = ((original_width - text_width) / 2, original_height + padding)
    
    # Draw text in black directly (no outline)
    try:
        # For newer Pillow versions
        draw.multiline_text(
            position,
            wrapped_text,
            font=font,
            fill=(0, 0, 0),  # Black text
            align="center"
        )
    except:
        # Fallback for older Pillow versions
        draw.multiline_text(
            position,
            wrapped_text,
            font=font,
            fill=(0, 0, 0),  # Black text
            align="center"
        )
    
    # Convert to bytes
    output = io.BytesIO()
    new_image.save(output, format="PNG")
    output.seek(0)
    
    return output

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
        
        # Call OpenAI agent (Dall-E) to generate meme image without text
        result = await agent_openai.generate_meme_from_concept(meme_concept)
        
        # Check if image generation failed due to content policy
        if result is None or not isinstance(result, dict):
            logger.warning(f"Content policy violation during meme generation: {result}")
            
            # Generate a humorous response
            humor_response = await agent_mistral.handle_content_policy_violation(meme_concept)
            await processing_msg.edit(content=humor_response)
            return
            
        # Extract image URL and text from result
        image_url = result["image_url"]
        meme_text = result["text"]
        
        # Check if we got a valid image URL
        if not image_url:
            await processing_msg.edit(content=f"Couldn't generate a meme. Please try again.")
            logger.error(f"No image URL returned for meme concept: {meme_concept}")
            return
        
        try:
            # Add text to the image using Pillow
            image_with_text = await add_text_to_image(image_url, meme_text)
            
            # Send the modified image as a file
            file = discord.File(fp=image_with_text, filename="meme.png")
            
            # Create an embed with the attached file
            embed = discord.Embed(title="Generated Meme", color=discord.Color.blue())
            embed.set_image(url="attachment://meme.png")
            embed.set_footer(text=f"Requested by {ctx.author.display_name}")
            
            # Send the meme
            await ctx.send(file=file, embed=embed)
            
        except Exception as e:
            logger.error(f"Error adding text to image: {e}")
            
            # Fallback to sending the image without text overlay
            embed = discord.Embed(title="Generated Meme", color=discord.Color.blue())
            embed.set_image(url=image_url)
            embed.set_footer(text=f"Requested by {ctx.author.display_name}")
                    
            await ctx.send(embed=embed)
            
        # Delete the processing message
        await processing_msg.delete()
        
    except Exception as e:
        logger.error(f"Error generating meme: {e}")
        error_message = f"Sorry, I encountered an error while generating the meme. Let's try again later!"
        
        # For debugging, include error details
        if os.getenv("DEBUG", "False").lower() == "true":
            error_message += f"\n\nError details: {str(e)}"
            
        await processing_msg.edit(content=error_message)

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
        
        # Call OpenAI agent (Dall-E) to generate meme image without text
        result = await agent_openai.generate_meme_from_concept(meme_concept)
        
        # Check if image generation failed due to content policy
        if result is None or not isinstance(result, dict):
            logger.warning(f"Content policy violation during spontaneous meme generation: {result}")
            
            # Generate a humorous response
            humor_response = await agent_mistral.handle_content_policy_violation(meme_concept)
            await processing_msg.edit(content=humor_response)
            return
            
        # Extract image URL and text from result
        image_url = result["image_url"]
        meme_text = result["text"]
        
        # Check if we got a valid image URL
        if not image_url:
            await processing_msg.edit(content=f"I changed my mind about that meme. The timing wasn't right.")
            logger.error(f"No image URL returned for spontaneous meme concept: {meme_concept}")
            return
        
        try:
            # Add text to the image using Pillow
            image_with_text = await add_text_to_image(image_url, meme_text)
            
            # Send the modified image as a file
            file = discord.File(fp=image_with_text, filename="meme.png")
            
            # Create an embed with the attached file
            embed = discord.Embed(title="Spontaneous Meme", color=discord.Color.green())
            embed.set_image(url="attachment://meme.png")
            embed.set_footer(text=f"Generated spontaneously based on your conversation")
            
            # Send the meme
            await message.channel.send(file=file, embed=embed)
            
        except Exception as e:
            logger.error(f"Error adding text to image: {e}")
            
            # Fallback to sending the image without text overlay
            embed = discord.Embed(title="Spontaneous Meme", color=discord.Color.green())
            embed.set_image(url=image_url)
            embed.set_footer(text=f"Generated spontaneously based on your conversation")
            
            # Let the user know we had to fall back
            embed.add_field(name="Note", value="Couldn't add text directly to image. Caption shown separately.", inline=False)
            
            await message.channel.send(embed=embed)
            
        # Delete the processing message
        await processing_msg.delete()
        
    except Exception as e:
        logger.error(f"Error generating spontaneous meme: {e}")
        await processing_msg.edit(content=f"I was going to make a meme, but I got distracted. Maybe next time!")

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
        reaction = await agent_mistral.react_to_latest(sentiment)
        
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