import os

from langchain_google_genai import ChatGoogleGenerativeAI


class ModelFactory:
    @staticmethod
    def get_fast():
        return ChatGoogleGenerativeAI(
            model="gemini-3-flash-preview",  # Updated for low-latency speed
            api_key=os.getenv("GOOGLE_API_KEY"),
            temperature=0,
        )

    @staticmethod
    def get_pro():
        return ChatGoogleGenerativeAI(
            model="gemini-3-pro-preview",  # Updated for deep reasoning
            api_key=os.getenv("GOOGLE_API_KEY"),
            temperature=0.1,
        )
