import os
from mistralai import Mistral
import discord
from openai import OpenAI
from collections import defaultdict
from typing import List, Dict
import logging

# Setup logging
logger = logging.getLogger(__name__)

MISTRAL_MODEL = "mistral-large-latest"
class MistralAgent:
    def __init__(self):
        MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
        self.client = Mistral(api_key=MISTRAL_API_KEY)
        self.chat_history = []
        self.max_chat_length = 5
        self.model = MISTRAL_MODEL

    def add_to_chat_history(self, message: discord.Message):
         self.chat_history.append({"author": message.author.name, "content": message.content})
         if len(self.chat_history) > self.max_chat_length:
            self.chat_history.pop(0)
 
    async def generate_meme_concept_from_chat_history(self):
        """
        Generate a concept for a meme based on recent chat history
        """
        try:
            history_text = "\n".join([
                f"{msg['author']}: {msg['content']}" 
                for msg in self.chat_history 
            ])

            # Log the history being sent to the model
            logger.info(f"Generating meme concept from history: {history_text[:200]}...")

            generate_meme_concept_messages = [
                {
                    "role": "system", 
                    "content": "You are a creative meme generator."
                },
                {
                    "role": "user", 
                    "content": f"""Come up with a concept for a funny meme based on the following chat history:

                    {history_text} 
                    
                    Structure your response exactly as follows:

                    IMAGE DESCRIPTION: [Describe a visual scene that exaggerates or creates an unexpected twist on something from the chat]
                    CAPTION: [A clever or ironic caption that delivers a punchline]

                    You MUST follow these guidelines for the caption:
                    - Keep it simple and concise
                    - Do not use any contractions
                    - Make sure it reads naturally and makes logical sense
                    - Do not use markdown formatting like asterisks or bold text
                    """
                }
            ]

            response = await self.client.chat.complete_async(
                model=MISTRAL_MODEL,
                messages=generate_meme_concept_messages,
            )

            meme_concept = response.choices[0].message.content
            logger.info(f"Generated meme concept: {meme_concept}")
            return meme_concept
            
        except Exception as e:
            logger.error(f"Error in generating meme concept: {str(e)}")
            raise Exception(f"Failed to generate meme concept: {str(e)}")
    
    async def handle_content_policy_violation(self):
        """
        Generate a humorous message when content policy violation occurs
        """
        try:            
            humor_response_messages = [
                {"role": "system", "content": "You are a witty, humorous AI assistant."},
                {"role": "user", "content": f"""
                Write a short, humorous message (2-3 sentences max) explaining why a meme couldn't be 
                generated due to content policy. Make it funny, like the AI is slightly embarrassed.
                
                Don't use phrases like "I apologize" or "I'm sorry" - just be light and humorous.
                Don't mention specific content policies - keep it vague and funny.
                
                Example: "Well, this chat was a little too spicy for me to generate a meme. Better luck next time hehe :)"
                """} 
            ]
            
            response = await self.client.chat.complete_async(
                model=MISTRAL_MODEL,
                messages=humor_response_messages,
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Error generating humorous response: {e}")
            return "Well, this chat was a little too spicy for me to generate a meme. Better luck next time hehe :)"

    async def decide_spontaneous_meme(self):
        """
        Decide whether to generate a meme spontaneously based on the chat history
        """
        try:
            # Format the chat history for the AI
            history_text = "\n".join([
                f"{msg['author']}: {msg['content']}" 
                for msg in self.chat_history 
            ])
            
            # Create a prompt for the AI to decide if a meme should be generated
            decision_prompt_messages = [
                {"role": "system", "content": "You are an assistant that decides whether to generate a meme based on chat context. You should be conservative and only suggest memes when truly appropriate. Spontaneous memes should be rare (less than 10% of conversations)."},
                {"role": "user", "content": f"""Here is the recent chat history:

{history_text}

Based ONLY on this conversation, decide if it's appropriate to generate a meme. 
Consider:
1. Is there a clear joke or reference that would make a good meme?
2. Is the conversation light-hearted enough for a meme?
3. Has enough context been established for a meme to make sense?
4. Would a meme add value to this conversation?

IMPORTANT: Spontaneous memes should be RARE - only generate them for truly meme-worthy conversations.

Respond with ONLY "YES" or "NO".
"""}
            ]
            
            decision_response = await self.client.chat.complete_async(
                model=MISTRAL_MODEL,
                messages=decision_prompt_messages,
            )

            decision = decision_response.choices[0].message.content.strip().upper()
            
            # If the AI decides to generate a meme, call the generate_meme method
            if decision == "YES":
                return True, "Decided to generate a meme for this conversation."
            else:
                return False, "Decided not to generate a meme for this conversation."
                
        except Exception as e:
            logger.error(f"Error in decide_spontaneous_meme: {str(e)}")
            return False, f"Error deciding whether to generate meme: {str(e)}"


class OpenAIAgent:
    def __init__(self):
        OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
        self.client = OpenAI(api_key=OPENAI_API_KEY)
        
    async def generate_meme_from_concept(self, meme_concept):
        """
        Generate a meme based on recent chat history in the specified channel.
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

    async def react_to_latest(self, channel_id: int, sentiment: str) -> str:
        """
        React to the latest message in the chat history for the specified channel.
        Optionally analyze the sentiment of the message if provided.
        
        Args:
            channel_id: The Discord channel ID
            sentiment: (optional) string of sentiment to react with
            
        Returns:
            A string with the reaction and optional sentiment analysis
        """
        # Get the chat history for this channel
        history = self.chat_history.get(channel_id, [])
        
        if not history:
            return "No chat history available to react to."
        
        # Get the latest message (Using queue, first is oldest)
        latest_message = history[-1]
        
        # Create a prompt for the AI to generate a reaction
        reaction_prompt_messages = [
            {"role": "system", "content": "You are a helpful assistant that reacts to messages with relevant emojis and brief comments."},
            {"role": "user", "content": f"""This is the latest message from {latest_message['author']}:
            
    "{latest_message['content']}"
            
    Please generate a reaction to this message. Your reaction should include:
    1. An appropriate emoji or set of emojis
    3. A brief comment (1-2 sentences) about the message

    {f'Also, please have your reaction be with the following sentiment which was specified by the user: {sentiment}' if sentiment else ''}
    """}
        ]
        
        # Get reaction from OpenAI
        reaction_response = self.client.chat.completions.create(
            model="gpt-4o",
            messages=reaction_prompt_messages
        )
        
        reaction = reaction_response.choices[0].message.content
        return reaction