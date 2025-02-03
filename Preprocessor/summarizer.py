import os
import time

import dotenv
from groq import Groq

from log import Logger

class Summarizer:
    def __init__(self, env_file="key.env"):
        """
        Initializes the Summarizer class with a specific model and configures the Groq API client.

        Args:
            env_file (str, optional): The environment file containing the API keys. Default is "key.env".
            model (str, optional): The model to use for summarization. If not provided, defaults to the model set in the environment.

        Attributes:
            model (str): The specified model for Groq.
            client (Groq): Instance of the Groq client for API requests.

        Returns:
            None

        Raises:
            KeyError: If the environment variables for the API keys cannot be found.
        """
        self.logger = Logger(self.__class__.__name__).get_logger()
        dotenv.load_dotenv(env_file, override=True)
        self.model = os.getenv("GROQ_MODEL_NAME")
        self.low_model = os.getenv("GROQ_LOW_MODEL_NAME")
        self.client = Groq()

    def claim_title_summarize(self, text, max_tokens=1024, temperature=0.5, stop=None):
        """
        Generates a summary for the given claim using the Groq API.

        Args:
            text (str): The text to summarize.
            max_tokens (int, optional): The maximum number of tokens for the completion. Default is 1024.
            temperature (float, optional): Controls randomness. Default is 0.5.
            stop (str or None, optional): Optional sequence indicating where the model should stop. Default is None.

        Returns:
            str: The summary generated by the model.

        Raises:
            Exception: If there is an error during the summarization process.
        """
        self.logger.info("Starting summarization process.")
        self.logger.info("Input text: %s...", text[:200]) 

        try:
            response = self.client.chat.completions.create(
                messages=[
                    {"role": "system", "content": """You are an AI designed to rephrase a claim into a concise, specific, and highly searchable query. 
                                                    Focus on preserving all critical details such as names, dates, locations, or key terms, but avoid unnecessary words. 
                                                    Provide only the text without any additional formatting only add at the beginning !g"""},
                    {"role": "user", "content": text}
                ],
                model=self.model,
                temperature=temperature,
                max_completion_tokens=max_tokens,
                stop=stop
            )

            summary = response.choices[0].message.content.strip()
            self.logger.info("Summarization completed successfully.")
            self.logger.info("Generated summary: %s...", summary[:1000])
            return summary

        except Exception as e:
            self.logger.error("Error generating summary: %s", e)
            return None
        
    def generate_summary(self, text, max_tokens=1024, temperature=0.5, stop=None):
        """
        Generates a summary for the given text using the specified model.

        Args:
            text (str): The text to be summarized.
            model (str): The model to be used for generating the summary.
            temperature (float): Sampling temperature (default: 0.7).
            max_tokens (int): Maximum number of tokens for the summary (default: 100).
            stop (str or list): Stop sequence(s) for the model (default: None).

        Returns:
            str: The generated summary.
        """
        response = self.client.chat.completions.create(
            messages=[
                {"role": "system", "content": """You are a summarizer, be specific. Don't use lists or bullet points. 
                                                Provide only the string without specifying that it is a summary.
                                                Translate in English."""},
                {"role": "user", "content": text}
            ],
            model=self.low_model,
            temperature=temperature,
            max_completion_tokens=max_tokens,
            stop=stop
        )
        return response.choices[0].message.content.strip()

    def summarize_texts(self, texts, max_tokens=1024, temperature=0.5, stop=None, token_cut = 20000, sleep_temperature=0.0003):
        """
        Generates summaries for a list of texts.

        Args:
            texts (list): List of strings to summarize.
            max_tokens (int, optional): Maximum number of tokens for each completion. Default is 1024.
            temperature (float, optional): Controls randomness. Default is 0.5.
            stop (str or None, optional): Optional sequence indicating where the model should stop. Default is None.

        Returns:
            list: A list of generated summaries.

        Raises:
            Exception: If there is an error during the batch summarization process.
        """
        self.logger.info("Starting batch summarization process for %d texts.", len(texts))
        summaries = []

        for index, text in enumerate(texts):
            self.logger.info("Summarizing text %d/%d...", index + 1, len(texts))
            self.logger.debug("Text %d content: %s", index + 1, text[:200])
            
            cutted_text = text[:token_cut]

            try:
                summary = self.generate_summary(
                                text=cutted_text,
                                max_tokens=max_tokens,
                                temperature=temperature,
                                stop=stop
                            )
                if summary:
                    summaries.append(summary)
                    self.logger.info("Text %d summarized successfully.", index + 1)
                    sleep_time = len(cutted_text)*sleep_temperature
                    self.logger.info("Sleep of %f seconds", sleep_time)
                    time.sleep(sleep_time)
                else:
                    self.logger.warning("No summary returned for text %d.", index + 1)
            except Exception as e:
                self.logger.error("Error summarizing text %d: %s", index + 1, str(e))
                summaries.append(None) 

        self.logger.info("Batch summarization process completed.")
        return summaries