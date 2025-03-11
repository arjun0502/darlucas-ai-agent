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

# Setup logging
logger = logging.getLogger(__name__)

# API configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY)


async def add_text_to_image(image_url, text):
    """
    Downloads an image from URL and adds text below the image with black text and reduced margins
    
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


async def generate_meme_from_concept(self, meme_concept):
        """
        Generate a meme based on recent chat history
        Returns image url without text and the text info separately
        """
        try:
            # Parse the structured meme concept
            image_description = ""
            meme_text = ""
            
            # Log the raw concept for debugging
            logger.info(f"Raw meme concept: {meme_concept}")
            
            # Handle Markdown formatting in the response
            clean_concept = meme_concept.replace("**", "")
            
            for line in clean_concept.split('\n'):
                # Use case-insensitive check and handle different variations
                if "IMAGE DESCRIPTION:" in line.upper():
                    image_description = line.replace("IMAGE DESCRIPTION:", "", 1).strip()
                elif "CAPTION:" in line.upper():
                    meme_text = line.replace("CAPTION:", "", 1).strip()
                        
            # Log the parsed components
            logger.info(f"Image Description: {image_description}")
            logger.info(f"Caption: {meme_text}")
            
            # Check if we have valid content
            if not image_description:
                logger.error("Failed to parse image description")
                # Try a fallback approach - take everything between IMAGE DESCRIPTION and CAPTION
                parts = clean_concept.upper().split("IMAGE DESCRIPTION:")
                if len(parts) > 1:
                    caption_parts = parts[1].split("CAPTION:")
                    if len(caption_parts) > 1:
                        image_description = caption_parts[0].strip()
                        logger.info(f"Fallback Image Description: {image_description}")
            
            if not meme_text:
                logger.error("Failed to parse caption")
                # Try a fallback approach
                parts = clean_concept.upper().split("CAPTION:")
                if len(parts) > 1:
                    meme_text = parts[1].strip()
                    logger.info(f"Fallback Caption: {meme_text}")
                        
            # Modified prompt for generating image WITHOUT text
            dalle_prompt = f"""Create a meme image given this description: {image_description}
    
    I NEED a simple, clean image with NO TEXT whatsoever."""
            
            # Log the prompt
            logger.info(f"DALL-E Prompt: {dalle_prompt[:200]}...")
            
            # Generate the meme with DALL-E
            image_response = self.client.images.generate(
                model="dall-e-3",
                prompt=dalle_prompt,
                size="1024x1024",
                quality="standard",
                n=1,
            )
        
            # Extract image URL and text from result
            image_url = image_response.data[0].url
            meme_text = meme_text
            
            # Check if we got a valid image URL
            if not image_url:
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
                
                return embed, file
            except Exception as e:
                logger.error(f"Error adding text to image: {str(e)}")
                
                # Fallback to returning the image without text overlay
                embed = discord.Embed(title="Generated Meme", color=discord.Color.blue())
                embed.set_image(url=image_url)
                
                # Add the caption as a field since we couldn't overlay it
                embed.add_field(name="Caption", value=meme_text, inline=False)
                
                return embed, None
        except Exception as e:
            logger.error(f"Error in generate_meme_from_concept: {str(e)}")
            
            # Check if this is a content policy violation and return None with the error
            if "content_policy_violation" in str(e):
                logger.warning(f"Content policy violation in meme generation: {meme_concept}")
                return None, str(e)
            
            # Re-raise for other types of errors
            raise Exception(f"Failed to generate meme: {str(e)}")
        
        
