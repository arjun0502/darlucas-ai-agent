import os
from mistralai import Mistral
import discord
from openai import OpenAI
from collections import defaultdict
from typing import List, Dict

MISTRAL_MODEL = "mistral-large-latest"
class MistralAgent:
    def __init__(self):
        MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
        self.client = Mistral(api_key=MISTRAL_API_KEY)
        self.chat_history = []
        self.max_chat_length = 15

    def add_to_chat_history(self, message: discord.Message):
         self.chat_history.append({"author": message.author.name, "content": message.content})
         if len(self.chat_history) > self.max_chat_length:
            self.chat_history.pop(0)
 

    async def generate_meme_concept_from_chat_history(self):
        """
        Generate a concept for a meme based on recent chat history
        """
        history_text = "\n".join([
            f"{msg['author']}: {msg['content']}" 
            for msg in self.chat_history 
        ])

        generate_meme_concept_messages = [
        {"role": "system", "content": "You are a creative meme generator. Create simple, funny memes with a single piece of text."},
        {"role": "user", "content": f"""Here is the recent chat history:

{history_text}

Create a funny meme concept based on this conversation. Structure your response exactly as follows:

IMAGE DESCRIPTION: [Describe the visual scene or background clearly without including any text]
TEXT: [The single piece of text that should appear in the meme]
PLACEMENT: [Where exactly the text should appear]

The meme should reference the conversation in a humorous way."""}
        ]

        response = await self.client.chat.complete_async(
            model=MISTRAL_MODEL,
            messages=generate_meme_concept_messages,
        )

        return response.choices[0].message.content
    

    async def decide_spontaneous_meme(self):
        """
        Decide whether to generate a meme spontaneously based on the chat history
        """
        # Format the chat history for the AI
        history_text = "\n".join([
            f"{msg['author']}: {msg['content']}" 
            for msg in self.chat_history 
        ])
        
        # Create a prompt for the AI to decide if a meme should be generated
        decision_prompt_messages = [
            {"role": "system", "content": "You are an assistant that decides whether to generate a meme based on chat context. You should be conservative and only suggest memes when truly appropriate. Spontaneous memes should be rare (less than 10% of messages)."},
            {"role": "user", "content": f"""Here is the recent chat history:

{history_text}

Based ONLY on this conversation, decide if it's appropriate to generate a meme. 
Consider:
1. Is there a clear joke or reference that would make a good meme?
2. Is the conversation light-hearted enough for a meme?
3. Has enough context been established for a meme to make sense?
4. Would a meme add value to this conversation?

IMPORTANT: Spontaneous memes should be RARE - only generate them for truly meme-worthy conversations. Also, make sure not to generate too many memes in a short period of time, unless it's a really good opportunity.

Respond with ONLY "YES" or "NO" followed by a concise yet informative explanation of your reasoning
"""}
        ]
        
        decision_response = await self.client.chat.complete_async(
            model=MISTRAL_MODEL,
            messages=decision_prompt_messages,
        )

        decision = decision_response.choices[0].message.content.strip().upper()
        print(decision.split()[0].strip("."))
        
        # If the AI decides to generate a meme, call the generate_meme methçod
        if decision.split()[0].strip(".") == "YES":
            return True, "Decided to generate a meme for this conversation:" + decision
        else:
            return False, "Decided not to generate a meme for this conversation:" + decision


class OpenAIAgent:
    def __init__(self):
        OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
        self.client = OpenAI(api_key=OPENAI_API_KEY)
        
    async def generate_meme_from_concept(self, meme_concept):
        """
        Generate a meme based on recent chat history in the specified channel.
        Returns image url
        """
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
        
        # Prompt for generating meme from DALL-E
        dalle_prompt = f"""Create a meme image with this exact specification:

1. IMAGE: {image_description}
2. TEXT: "{meme_text}" - PLACEMENT: {text_placement}

The text must be must be used and displayed exactly with no typos.

I NEED to test how the tool works with extremely simple prompts. DO NOT add any detail, just use it AS-IS:"""
        
        # Generate the meme with DALL-E
        image_response = self.client.images.generate(
            model="dall-e-3",
            prompt=dalle_prompt,
            size="1024x1024",
            quality="standard",
            n=1,
        )
        
        # Return the image URL
        return image_response.data[0].url
