import os
import json
import logging
import discord
import re
import aiohttp
from io import BytesIO
import textwrap
from PIL import Image, ImageDraw, ImageFont
import asyncio
from typing import Union, Tuple, Optional
from openai import OpenAI
from dotenv import load_dotenv
import io

# Setup logging
logger = logging.getLogger(__name__)

# API configuration
load_dotenv()  # This loads variables from a .env file into environment variables
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY)

async def add_caption_to_image(image_url, caption):
    """
    Adds caption to image
    
    Args:
        image_url: URL of the image to download
        text: Text to add to the image
        
    Returns:
        BytesIO object containing the modified image
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

    caption = caption.upper()
    
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
    
    wrapped_text = textwrap.fill(caption, width=chars_per_line)
    
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


async def handle_error(error):
    """
    Generate a humorous message when content policy violation occurs
    """
    try:            
        HUMOR_REPONSE_PROMPT = [
            {"role": "system", "content": "You are a witty, humorous AI assistant."},
            {"role": "user", "content": f"""
            Write a short, humorous message (2-3 sentences max) explaining why a meme couldn't be 
            generated due to {error}. Make it funny, like the AI is slightly embarrassed.
            
            Don't use phrases like "I apologize" or "I'm sorry" - just be light and humorous.
            Don't mention specific content policies - keep it vague and funny.
            
            Example: "Well, this chat was a little too spicy for me to generate a meme. Better luck next time hehe :)"
            """} 
        ]
        
        response = await client.chat.complete_async(
            model="gpt-4o-mini",
            messages=HUMOR_REPONSE_PROMPT,
        )
    
        text_response = response.choices[0].message.content

        DALLE_PROMPT = f"""Create a meme image given this description: {text_response}

        I NEED a simple, clean image with NO TEXT whatsoever."""

        # Generate the meme with DALL-E
        image_response = client.images.generate(
            model="dall-e-3",
            prompt=DALLE_PROMPT,
            size="1024x1024",
            quality="standard",
            n=1,
        )

        image_url = image_response.data[0].url

        try:
            # Add text to the image using Pillow
            image_with_text = await add_caption_to_image(image_url, text_response)
        
            # Send the modified image as a file
            file = discord.File(fp=image_with_text, filename="meme.png")
            
            # Create an embed with the attached file
            embed = discord.Embed(title="Oopsies", color=discord.Color.blue())
            embed.set_image(url="attachment://meme.png")
            
            return embed, file
        
        except Exception as e:
            logger.error(f"Error adding text to image: {str(e)}")
            
            # Fallback to returning the image without text overlay
            embed = discord.Embed(title="Oopsies", color=discord.Color.blue())
            embed.set_image(url=image_url)
            
            # Add the caption as a field since we couldn't overlay it
            embed.add_field(name="Caption", value=text_response, inline=False)
            
            return embed, None
    
    except Exception as e:
        logger.error(f"Error generating humorous response: {e}")
        # Use a local file for the fallback image
        fallback_file = discord.File("/Users/danielguo/School/darlucas-ai-agent/fallback_error.png", filename="fallback.png")
        embed = discord.Embed(title="Oopsies", color=discord.Color.blue())
        embed.set_image(url="attachment://fallback.png")
        
        return embed

async def generate_meme(image_description, caption):
        """
        Generate a meme based on recent chat history
        Returns image url without text and the text info separately
        """
        try:
            # Modified prompt for generating image WITHOUT text
            DALLE_PROMPT = f"""Create a meme image given this description: {image_description}
    
    I NEED a simple, clean image with NO TEXT whatsoever."""
            
            # Log the prompt
            logger.info(f"DALL-E Prompt: {DALLE_PROMPT[:200]}...")
            
            # Generate the meme with DALL-E
            image_response = client.images.generate(
                model="dall-e-3",
                prompt=DALLE_PROMPT,
                size="1024x1024",
                quality="standard",
                n=1,
            )
        
            # Extract image URL and text from result
            image_url = image_response.data[0].url
            
            # Check if we got a valid image URL
            if not image_url:
                logger.error(f"No image URL returned for meme")
                return
            
            try:
                # Add text to the image using Pillow
                image_with_text = await add_caption_to_image(image_url, caption)
                
                # Send the modified image as a file
                file = discord.File(fp=image_with_text, filename="meme.png")
                
                # Create an embed with the attached file
                embed = discord.Embed(title="Generated Meme", color=discord.Color.blue())
                embed.set_image(url="attachment://meme.png")
                
                return embed, file
            except Exception as e:
                logger.error(f"Error adding text to image: {str(e)}")
                
                # Fallback to returning the image without text overlay
                embed = discord.Embed(title="Generated Meme", color=discord.Color.blue())
                embed.set_image(url=image_url)
                
                # Add the caption as a field since we couldn't overlay it
                embed.add_field(name="Caption", value=caption, inline=False)
                
                return embed, None
            
        except Exception as e:
            logger.error(f"Error in generate_meme_from_concept: {str(e)}")
            return await handle_error(e)
        
        
