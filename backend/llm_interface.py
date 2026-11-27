import os
from dotenv import load_dotenv
from groq import Groq

load_dotenv()
client = Groq(
    api_key=os.getenv("GROQ_API_KEY"),
)

chat_completion = client.chat.completions.create(
    messages=[
        {
            "role": "user",
            "content": "Explain the importance of fast language models",
        }
    ],
    model="openai/gpt-oss-120b",
)

print(chat_completion.choices[0].message.content)

class LLMInterface:
    """Class responsible for communication with the LLM model."""

    def __init__(self):
        pass

    def send_message(self):
        pass