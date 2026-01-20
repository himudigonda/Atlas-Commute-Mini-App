import os

from langchain_google_genai import (
    ChatGoogleGenerativeAI,
    HarmBlockThreshold,
    HarmCategory,
)


class ModelFactory:
    @staticmethod
    def _get_base_config(model: str, temp: float):
        return ChatGoogleGenerativeAI(
            model=model,
            api_key=os.getenv("GOOGLE_API_KEY"),
            temperature=temp,
            convert_system_message_to_human=True,
            # Rule 40: Maximize responsiveness by loosening safety for utility
            safety_settings={
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
            },
        )

    @staticmethod
    def get_fast():
        # Rule: Use 1.5-flash for stable, production-grade extraction
        return ModelFactory._get_base_config("gemini-3-flash-preview", 0)

    @staticmethod
    def get_pro():
        # Rule: Use 1.5-pro for stable, deep reasoning
        return ModelFactory._get_base_config("gemini-3-flash-preview", 0.1)
