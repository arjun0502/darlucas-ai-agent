import os
from openai import OpenAI
import discord
from collections import defaultdict
from typing import List, Dict
import logging

# Setup logging
logger = logging.getLogger(__name__)

class OpenAIAgent:
    def __init__(self):
        OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
        self.client = OpenAI(api_key=OPENAI_API_KEY)
        
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
            
            # Return the image URL and the caption
            return {
                "image_url": image_response.data[0].url,
                "text": meme_text,
            }
                
        except Exception as e:
            logger.error(f"Error in generate_meme_from_concept: {str(e)}")
            
            # Check if this is a content policy violation and return None with the error
            if "content_policy_violation" in str(e):
                logger.warning(f"Content policy violation in meme generation: {meme_concept}")
                return None, str(e)
            
            # Re-raise for other types of errors
            raise Exception(f"Failed to generate meme image: {str(e)}")
