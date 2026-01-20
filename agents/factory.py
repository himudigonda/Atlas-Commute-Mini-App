import os
from langchain_google_genai import ChatGoogleGenerativeAI

class ModelFactory:
    @staticmethod
    def get_fast():
        return ChatGoogleGenerativeAI(
            model="gemini-1.5-flash",
            api_key=os.getenv("GOOGLE_API_KEY"),
            temperature=0
        )

    @staticmethod
    def get_pro():
        return ChatGoogleGenerativeAI(
            model="gemini-1.5-pro",
            api_key=os.getenv("GOOGLE_API_KEY"),
            temperature=0.1
        )
