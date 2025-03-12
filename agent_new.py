import os
import json
import logging
from typing import Dict, List, Optional
import discord
import random
from datetime import datetime, timedelta

# Set up logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("meme_agent.log")
    ]
)

from mistralai import Mistral
from tools.generate import generate_meme
from tools.search import search_meme

logger = logging.getLogger("discord")

MISTRAL_MODEL = "mistral-large-latest"
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")

SYSTEM_PROMPT = """
You are an intelligent meme assistant. First, look at the latest message and determine whether the user is EXPLICITLY requesting a meme.

## Tool Selection

If they explicitly request a meme, determine which tool to use:

### Use `search_meme` when:
- User is looking for a specific existing meme or meme format
- Examples:
  - "Get the meme with multiple spidermen pointing at each other"
  - "Send the capybara meme"
  - "Give me the two buttons meme"
  - "Find the 'distracted boyfriend' meme"
  - "Show me the 'change my mind' meme format"
  - "I need that meme where the dog is sitting in the burning house saying 'this is fine'"
  - "Can I see the 'drake hotline bling' meme template?"
  - "Get me the 'galaxy brain' meme"
  - "Find that meme with Kermit drinking tea"
  - "Show the 'woman yelling at cat' meme"

### Use `generate_meme` when:
- User wants a custom or new meme
- User asks to "create," "make," or "generate" a meme
- Request includes specific elements to combine in a novel way
- Examples:
  - "Make a meme about my coding project failing"
  - "Create a funny meme about AI"
  - "Generate a meme about working from home"
  - "Make a meme about debugging at 3am"
  - "Create something about waiting for code to compile"
  - "Generate a meme that captures how it feels when the boss asks for last-minute changes"
  - "Make a funny meme about my plants dying despite my best efforts"
  - "Create a meme about spending too much time on social media"
  - "Generate something about pretending to work during video calls"
  - "Make a meme about trying to explain tech to my parents"

## Parameter Determination

Once you've selected the tool, determine the parameters:

### For search_meme:
- Extract specific keywords from the request for the query parameter
- If request is generic, review conversation history for relevant context
- Focus on subject matter and emotional tone
- Keep keywords concise and relevant
- Examples:
  - "Find a meme about cats knocking things off tables" → query: "cats knocking things off tables"
  - "Show me a programming meme" → query: "programming"
  - After discussion about job interviews: "Show me a relevant meme" → query: "job interview"
  - After talking about Monday mornings: "I need a meme for this" → query: "Monday morning tired"
  - "Get me a meme about waiting" → query: "waiting impatient"

### For generate_meme:
- Create image description and caption based on request or conversation context
- For specific requests, use the explicit topics mentioned
- For generic requests, review conversation history to determine relevant themes
- Keep captions brief, avoid contractions, and ensure they read naturally
- Examples:
  - "Make a meme about slipping on bananas" →
    - image: "person confidently walking then dramatically slipping on banana peel"
    - caption: "ME EXPLAINING MY FIVE YEAR PLAN / THE UNIVERSE"
  - After discussing debugging: "Make a funny meme" →
    - image: "person staring intensely at computer screen with messy hair and empty coffee cups"
    - caption: "WHEN THE BUG DISAPPEARS AFTER YOU REMOVE THE CODE THAT FIXES IT"
  - "Create a meme about my fitness journey" →
    - image: "person excitedly buying gym equipment then using it as clothes hanger"
    - caption: "DAY 1 OF FITNESS JOURNEY / DAY 2 OF FITNESS JOURNEY"

## EXTREMELY LIMITED Spontaneous Meme Generation

**IMPORTANT: DEFAULT TO NOT GENERATING A MEME UNLESS EXPLICITLY REQUESTED!**

If the user is NOT explicitly requesting a meme, spontaneous meme generation should be EXTREMELY RARE. The vast majority of messages should NOT trigger meme generation. When in doubt, DO NOT generate a meme.

Consider these strict criteria - ALL must be met before generating a spontaneous meme:
1. Is there an obvious joke or reference that is practically begging to be made into a meme?
2. Is the conversation clearly casual and light-hearted?
3. Has sufficient context been established so that a meme would make perfect sense?
4. Would a meme genuinely enhance the conversation rather than interrupt it?
5. Has it been a significant time since any meme was shared in the conversation?

For spontaneous memes, always use generate_meme and base parameters on recent conversation context.

Examples of the RARE appropriate opportunities for spontaneous memes:
- User: "I just spent 3 hours debugging only to find I had a typo in a variable name"
- User: "My cat knocked my coffee onto my keyboard right before my important presentation"
- User: "The client loved my presentation but then asked for completely different features"

Examples of common inappropriate times for spontaneous memes (DO NOT generate memes for these):
- User: "Can you help me understand this error message?"
- User: "I'm trying to solve this complex problem with my database"
- User: "Could you explain how this algorithm works?"
- User: "What do you think about this approach?"
- User: "I'm not sure what's causing this issue"
- User: "How would you implement this feature?"

## Chat History

The chat history is provided below between triple backticks.

```
{chat_history_context}
```

Carefully analyze the chat history when deciding whether to generate a meme. In most cases, the correct decision will be to NOT generate a meme unless explicitly requested.

## Humor Style Guidelines

When a meme is appropriate (either requested or in the extremely rare case of spontaneous generation), create absurdist Gen Z memes with these characteristics:
- Deadpan delivery of bizarre statements
- Surreal juxtapositions that make no logical sense yet feel right
- Anti-humor where the punchline deliberately disappoints or confuses
- Captions that start normal but end with unrelated conclusions
- Random elements that have nothing to do with the setup
- Abrupt emotional tone shifts mid-caption
- Existential crises in mundane situations
- Made-up words that sound like they could be real (like "conpentpine")
- Self-referential humor about meme culture itself

## FINAL REMINDER

**YOU SHOULD ONLY GENERATE MEMES WHEN APPROPRIATE, WHICH SHOULD BE RARE!**

DO NOT disrupt the flow of conversation among the users in the channel. You should be a passive observer of the chat in most cases, only responding when:
1. A user explicitly requests a meme
2. A truly exceptional opportunity for a spontaneous meme arises (which should be extremely rare)

When in doubt, do not generate a meme.
"""

class MemeAgent:
    def __init__(self):
        self.client = Mistral(api_key=MISTRAL_API_KEY)
        self.chat_history = []
        self.max_history_len = 10   

        self.tools = [
            {
                "type": "function",
                "function": {
                    "name": "search_meme",
                    "description": "retrieves meme from Humor API either based on user input or chat history",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": 
                            {"type": "string", 
                             "description": "the search query/keywords from the user for Humor API"
                            }
                        },
                        "required": ["query"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "generate_meme",
                    "description": "generates meme based on user input or chat history",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "image_description": 
                            {"type": "string", 
                             "description": "description of image to generate"
                             },
                            "caption": 
                            {"type": "string", 
                             "description": "caption to go along with meme"}
                        },
                        "required": ["image_description", "caption"]
                    }
                }
            },
        ]

        self.tools_to_functions = {
            "search_meme": search_meme,
            "generate_meme": generate_meme,
        }
    
    def add_to_chat_history(self, message: discord.Message):
        """Add a message to the chat history"""
        self.chat_history.append({
            "author": message.author.name, 
            "content": message.content, 
            "timestamp": datetime.now().isoformat()
        })
        if len(self.chat_history) > self.max_history_len:
            self.chat_history.pop(0)
    
    def format_chat_history(self) -> str:
        """Format the chat history for inclusion in the system prompt"""
        if not self.chat_history:
            return "## Recent Chat History\nNo recent chat history available."
        
        formatted_history = "## Recent Chat History\n"
        for idx, msg in enumerate(self.chat_history):
            formatted_history += f"{idx+1}. {msg['author']}: {msg['content']}\n"
        
        return formatted_history
    
    async def run(self, message: discord.Message):
        # Add the current message to chat history
        self.add_to_chat_history(message)
        
        # Format chat history for inclusion in system prompt
        chat_history_context = self.format_chat_history()
        
        # Apply chat history to system prompt
        system_prompt = SYSTEM_PROMPT.format(chat_history_context=chat_history_context)
        
        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": f"This is the latest message from user {message.author}: {message.content}\nDecide what to do according to tools available to you. You should only take actions and use the tools if appropriate. Most of the time, you are a passive observer of the chat.",
            },
        ]

        try:
            logger.info(f"Processing message from {message.author.name}: '{message.content}'")
            logger.info(f"Using chat history context with {len(self.chat_history)} messages")
            
            # Send request to Mistral API
            logger.info(f"Sending request to Mistral API")
            tool_response = await self.client.chat.complete_async(
                model=MISTRAL_MODEL,
                messages=messages,
                tools=self.tools,
                tool_choice="any",
            )

            messages.append(tool_response.choices[0].message)
            
            # Check if tool_calls exists and is not empty
            if not tool_response.choices[0].message.tool_calls:
                logger.error("No tool calls in response")
                await message.reply("Sorry, I couldn't process that request. Please try again.")
                return

            tool_call = tool_response.choices[0].message.tool_calls[0]
            function_name = tool_call.function.name
            function_params = json.loads(tool_call.function.arguments)
            
            # Log the selected tool and parameters
            logger.info(f"Tool selected: {function_name}")
            logger.info(f"Tool parameters: {json.dumps(function_params, indent=2)}")
            
            if function_name not in self.tools_to_functions:
                logger.error(f"Unknown function: {function_name}")
                await message.reply(f"Sorry, I don't know how to {function_name}. Please try again.")
                return
            
            # Send loading message based on function name
            loading_text = "Searching for a meme..." if function_name == "search_meme" else "Generating a meme..."
            loading_message = await message.reply(loading_text)
            
            logger.info(f"Executing {function_name} with provided parameters")
            function_result = await self.tools_to_functions[function_name](**function_params)

            if isinstance(function_result, tuple):
                embed, file = function_result
                logger.info(f"Sending response with file and embed to {message.author.name}")
                await loading_message.delete()  # Delete the loading message
                await message.reply(file=file, embed=embed)
            else:
                logger.info(f"Sending embed response to {message.author.name}")
                await loading_message.delete()  # Delete the loading message
                await message.reply(embed=function_result)
            
            logger.info(f"Successfully processed request from {message.author.name}")
                
        except Exception as e:
            logger.error(f"Error in MemeAgent.run: {e}", exc_info=True)
            # If there was a loading message try to delete it
            try:
                if 'loading_message' in locals():
                    await loading_message.delete()
            except:
                pass
            await message.reply(f"Sorry, something went wrong: {str(e)}")