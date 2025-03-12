import os
import json
import logging
from typing import Dict, List, Optional
import discord
from datetime import datetime

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
In most cases, you should NOT call any tools and just be a PASSIVE OBSERVER. Only call a tool if a meme is explicitly requested or if ALL spontaneous meme criteria are met (which is extremely rare, <2% of messages). If you decide no meme is needed, simply respond with 'NO_ACTION' and nothing else.

## Core Behavior Rules

1. **DEFAULT STATE: NO TOOL CALL**
   - Do NOT call tools unless EXPLICITLY requested by user or, in the rare chance, decide to spontaneously generate a meme
   - The vast majority of messages should just have NO tool call

2. **EXPLICIT REQUESTS ONLY**
   - ONLY generate memes when users EXPLICITLY ask for one using clear language
   - Valid triggers: "make a meme", "generate a meme", "create a meme", "find a meme", "show me a meme", "give me a meme"
   - If a request is ambiguous, DO NOT generate a meme

3. **SPONTANEOUS MEMES: NEARLY NEVER**
   - Spontaneous meme generation should be EXTREMELY RARE (less than 2% of messages)
   - ALL criteria listed below must be met for spontaneous generation
   - If ANY criterion is not met, do not make a tool call

## Request Analysis and Tool Selection

First, analyze ONLY THE LAST USER MESSAGE to determine if a meme is explicitly requested:

### Use `search_meme` when:
- User is looking for a specific existing meme or meme format
- Examples:
  - "Get the meme with multiple spidermen pointing at each other"
  - "capybara meme"
  - "Can you get me meme where drake is like huh"
  - "Find a meme" (will require extracting topic from conversation history)

### Use `generate_meme` when:
- User wants a custom or new meme
- User asks to "create," "make," or "generate" a meme
- Examples:
  - "Make a meme about Rainbow Road on Mario Kart being super hard"
  - "Create a meme about me not wanting to do homework"
  - "Generate a meme" (this requires extracting topic from conversation history)

## Parameter Extraction (ONLY AFTER determining a meme is appropriate)

### For search_meme:
- PRIMARY SOURCE: Extract specific keywords from the LAST USER MESSAGE if it contains topic details
- SECONDARY SOURCE: If last message only contains a simple request ("show me a meme", "find a meme"), THEN examine the RECENT CONVERSATION HISTORY to determine the relevant topic
- Focus on subject matter and visual elements mentioned
- Remove unnecessary words like "find", "get", "show me"
- Examples:
  - Direct request: "Can you find me that meme with the guy blinking in disbelief?" → query: "blinking guy disbelief"
  - Context-based: After discussion about job interviews, user says "Show me a meme" → query: "job interview stress" (extracted from conversation)
  - Direct request: "I need that distracted boyfriend meme" → query: "distracted boyfriend"
  - Context-based: After talking about gaming, user says "Find a relevant meme" → query: "video game frustration" (extracted from conversation)

### For generate_meme:
- PRIMARY SOURCE: Extract topic and details from the LAST USER MESSAGE if it contains specific topic
- SECONDARY SOURCE: If last message only contains a simple request ("make a meme", "generate a meme"), THEN examine the RECENT CONVERSATION HISTORY to determine the most relevant topic
- Be specific about the image description and caption
- Examples:
  - Direct request: "Make a meme about debugging at 3am" →
    - image: "programmer with bloodshot eyes staring at computer screen surrounded by empty coffee cups in dark room"
    - caption: "ME AT 3AM WHEN THE BUG I'VE BEEN CHASING FOR 5 HOURS WAS A TYPO"
  - Context-based: After discussing plant care problems, user says "Generate a meme" →
    - image: "person lovingly watering plant while plant dramatically wilts"
    - caption: "MY PLANTS RECEIVING THE PERFECT AMOUNT OF WATER AND SUNLIGHT / MY PLANTS CHOOSING DEATH ANYWAY"

## Spontaneous Meme Criteria (ALL MUST BE MET TO TRIGGER A TOOL CALL)

For the RARE cases where spontaneous generation might be appropriate, ALL these criteria must be met:

1. **Obvious Meme Opportunity**: The conversation history contains a clear comedic setup that is BEGGING for a meme response
2. **Conversation Enhancement**: A meme would genuinely add value rather than disrupt the flow. For example, if a user is clearly awaiting a response from a different user, DO NOT generate a meme.


## FINAL VERIFICATION CHECK

Before responding with ANY meme, perform this final check:
1. Is the user EXPLICITLY asking for a meme using clear language in the LAST MESSAGE? If NO, most likely remain silent.
2. If considering spontaneous generation, have ALL FOUR criteria been fully met when analyzing BOTH the LAST MESSAGE and CONVERSATION HISTORY? If ANY are not met, remain silent.

IMPORTANT: In most cases, you should NOT call any tools. Only call a tool if a meme is explicitly requested or if ALL spontaneous meme criteria are met (which is extremely rare, <2% of messages). If you decide no meme is needed, simply respond with 'NO_ACTION' and nothing else.

{chat_history_context}
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
        """Process a Discord message and potentially generate a meme response"""
        try:
            # Add the current message to chat history
            self.add_to_chat_history(message)
            
            # Format chat history for inclusion in system prompt
            chat_history_context = self.format_chat_history()
            
            # Apply chat history to system prompt
            system_prompt = SYSTEM_PROMPT.format(chat_history_context=chat_history_context)
            
            # Prepare messages for LLM
            messages = [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": f"This is the latest message from user {message.author}: {message.content}\n\nYour default behavior is to not call any tools. Only use a tool if the message explicitly requests a meme or if all spontaneous meme criteria are fully met (which should be extremely rare). After deciding what to do, concisely explain your decision and thought process on why you decided to act, and why you chose the tool you did."
                },
            ]

            # Log request information
            logger.info(f"Processing message from {message.author.name}: '{message.content}'")
            
            # Request to Mistral
            response = await self.client.chat.complete_async(
                model=MISTRAL_MODEL,
                messages=messages,
                tools=self.tools,
                tool_choice="auto",  
            )
            
            # Get the model's response
            model_response = response.choices[0].message
            
            # Check if the model chose to use a tool
            if not model_response.tool_calls:
                # Model chose not to use any tools - this is expected for most messages
                logger.info("Model chose not to generate a meme")
                # Check if the response is just 'NO_ACTION'
                if model_response.content and model_response.content.strip() == "NO_ACTION":
                    logger.info("Model returned NO_ACTION response")
                    return
                if model_response.content:
                    logger.info(f"Model returned content: {model_response.content}")
                return
            
            # If we get here, the model decided to use a tool
            tool_call = model_response.tool_calls[0]
            function_name = tool_call.function.name
            
            # Parse the function parameters
            try:
                function_params = json.loads(tool_call.function.arguments)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse function arguments: {e}")
                await message.reply("Sorry, there was an error processing your meme request.")
                return
            
            # Log the tool selection
            logger.info(f"Tool selected: {function_name}")
            logger.info(f"Tool parameters: {json.dumps(function_params, indent=2)}")
            
            # Validate the function name
            if function_name not in self.tools_to_functions:
                logger.error(f"Unknown function: {function_name}")
                await message.reply(f"Sorry, I don't know how to {function_name}. Please try again.")
                return
            
            # Send a loading message
            loading_text = "Searching for a meme..." if function_name == "search_meme" else "Generating a meme..."
            loading_message = await message.reply(loading_text)
            
            try: 
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
                
                messages.append(response.choices[0].message)
                messages.append(
                    {
                        "role": "tool",
                        "name": function_name,
                        "content": "Successfully processed request from user",
                        "tool_call_id": tool_call.id,
                    }
                )

                # Run the model again with the tool call and its result.
                new_response = await self.client.chat.complete_async(
                    model=MISTRAL_MODEL,
                    messages=messages,
                )

                logger.info(new_response.choices[0].message.content)
            
                if function_result is None:
                    logger.info(f"No result from {function_name}")
                    await message.reply("I couldn't find a relevant meme. Let me try to generate one for you instead!")
                    messages.append(
                        {
                            "role": "user",
                            "content": f"You couldn't find a relevant meme. Try to generate one for me instead using the generate_meme tool."
                        },
                    )
                    logger.info(f"Sending request to Mistral API")
                    tool_response = await self.client.chat.complete_async(
                        model=MISTRAL_MODEL,
                        messages=messages,
                        tools=self.tools,
                        tool_choice="auto",
                    )
                    
                    # Check if tool_calls exists and is not empty
                    if not tool_response or tool_response.choices[0].message.tool_calls:
                        logger.error("No tool calls in response")
                        await message.reply("Sorry, I couldn't process that request. Please try again.")
                        return

                    tool_call = tool_response.choices[0].message.tool_calls[0]
                    function_name = tool_call.function.name
                    function_params = json.loads(tool_call.function.arguments)
                    function_result = await self.tools_to_functions[function_name](**function_params)

            except Exception as e:
                logger.error(f"Error executing {function_name}: {e}", exc_info=True)
                # Try to delete loading message if it exists
                try:
                    await loading_message.delete()
                except Exception:
                    pass
                await message.reply(f"Sorry, I couldn't process your meme request: {str(e)}")
                
        except Exception as e:
            logger.error(f"Error in MemeAgent.run: {e}", exc_info=True)
            await message.reply(f"Sorry, something went wrong: {str(e)}")