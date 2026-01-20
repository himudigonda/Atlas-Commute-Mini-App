import os

from langchain_google_genai import ChatGoogleGenerativeAI


class ModelFactory:
    @staticmethod
    def get_fast():
        return ChatGoogleGenerativeAI(
            model="gemini-2.0-flash",  # Updated for low-latency speed
            api_key=os.getenv("GOOGLE_API_KEY"),
            temperature=0,
        )

    @staticmethod
    def get_pro():
        return ChatGoogleGenerativeAI(
            model="gemini-2.0-pro-exp-02-05",  # Updated for deep reasoning
            api_key=os.getenv("GOOGLE_API_KEY"),
            temperature=0.1,
        )
