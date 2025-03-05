import os
from mistralai import Mistral
import discord
from openai import OpenAI
from collections import defaultdict
from typing import List, Dict

MISTRAL_MODEL = "mistral-large-latest"
SYSTEM_PROMPT = "You are a helpful assistant."


class MistralAgent:
    def __init__(self):
        MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")

        self.client = Mistral(api_key=MISTRAL_API_KEY)

    async def run(self, message: discord.Message):
        # The simplest form of an agent
        # Send the message's content to Mistral's API and return Mistral's response

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": message.content},
        ]

        response = await self.client.chat.complete_async(
            model=MISTRAL_MODEL,
            messages=messages,
        )

        return response.choices[0].message.content

# Maximum number of messages to store per channel
MAX_HISTORY_LENGTH = 5

class OpenAIAgent:
    def __init__(self):
        # Initialize OpenAI client
        OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
        self.client = OpenAI(api_key=OPENAI_API_KEY)
        
        # Store chat history as a dictionary of channel IDs to lists of messages
        # defaultdict automatically creates an empty list for new channel IDs
        self.chat_history: Dict[int, List[discord.Message]] = defaultdict(list)
        

    def add_to_history(self, message: discord.Message):
        """
        Add a message to the chat history for its channel.
        If the history exceeds MAX_HISTORY_LENGTH, remove the oldest message.
        """
        channel_id = message.channel.id
        
        # Add the new message to the history
        self.chat_history[channel_id].append({
            "author": message.author.name,
            "content": message.content,
            "timestamp": message.created_at.isoformat()
        })
        
        # Keep only the most recent MAX_HISTORY_LENGTH messages
        if len(self.chat_history[channel_id]) > MAX_HISTORY_LENGTH:
            self.chat_history[channel_id].pop(0)

    async def generate_meme(self, channel_id: int) -> tuple:
        """
        Generate a meme based on recent chat history in the specified channel.
        Returns a tuple of (image_url, prompt_used)
        """
        # Get the chat history for this channel
        history = self.chat_history.get(channel_id, [])
        
        if not history:
            return None, "No chat history available to create a meme from."
        
        # Format the chat history for the AI
        history_text = "\n".join([
            f"{msg['author']}: {msg['content']}" 
            for msg in history 
        ])
        
        # Create a prompt for the AI to generate a structured meme concept
        meme_prompt_messages = [
            {"role": "system", "content": "You are a creative meme generator. Create simple, funny memes with a single piece of text."},
            {"role": "user", "content": f"""Here is the recent chat history:

{history_text}

Create a funny meme concept based on this conversation. Structure your response exactly as follows:

IMAGE DESCRIPTION: [Describe the visual scene or background clearly without including any text]
TEXT: [The single piece of text that should appear in the meme]
PLACEMENT: [Where exactly the text should appear]

The meme should reference the conversation in a humorous way."""}
        ]
        
        # Get meme concept from OpenAI
        meme_concept_response = self.client.chat.completions.create(
            model="gpt-4o",
            messages=meme_prompt_messages
        )
        
        meme_concept = meme_concept_response.choices[0].message.content
        
        # Parse the structured meme concept
        image_description = ""
        meme_text = ""
        text_placement = ""
        
        for line in meme_concept.split('\n'):
            if line.startswith("IMAGE DESCRIPTION:"):
                image_description = line.replace("IMAGE DESCRIPTION:", "").strip()
            elif line.startswith("TEXT:"):
                meme_text = line.replace("TEXT:", "").strip()
            elif line.startswith("PLACEMENT:"):
                text_placement = line.replace("PLACEMENT:", "").strip()
        
        # Craft a simple DALL-E prompt with a single text element
        dalle_prompt = f"""Create a meme image with this exact specification:

1. IMAGE: {image_description}
2. TEXT: "{meme_text}" - PLACEMENT: {text_placement}

The text must be must be used and displayed exactly with no typos.

I NEED to test how the tool works with extremely simple prompts. DO NOT add any detail, just use it AS-IS:"""
        
        # Generate the image with DALL-E 3
        image_response = self.client.images.generate(
            model="dall-e-3",
            prompt=dalle_prompt,
            size="1024x1024",
            quality="standard",
            n=1,
        )
        
        # Return the image URL and the concept used
        return image_response.data[0].url, meme_concept

    def decide_spontaneous_meme(self, channel_id: int) -> tuple:
        """
        Generate a meme spontaneously based on the chat history.
        """
        # Get the chat history for this channel
        history = self.chat_history.get(channel_id, [])

        if not history:
            return False, "No chat history available to create a meme from."
        
        # Format the chat history for the AI
        history_text = "\n".join([
            f"{msg['author']}: {msg['content']}" 
            for msg in history 
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
        
        # Get decision from OpenAI
        decision_response = self.client.chat.completions.create(
            model="gpt-4o",
            messages=decision_prompt_messages
        )
        
        decision = decision_response.choices[0].message.content.strip().upper()
        
        # If the AI decides to generate a meme, call the generate_meme method
        if decision == "YES":
            return True, "Decided to generate a meme for this conversation."
        else:
            return False, "Decided not to generate a meme for this conversation."
