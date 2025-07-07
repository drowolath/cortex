import litellm
from .logger import get_logger

logger = get_logger("litellm")


def prompt_llm(message: str, model: str = "gpt-3.5-turbo") -> str:
    """
    Simple function to prompt an LLM with a message.
    """
    try:
        response = litellm.completion(
            model=model, messages=[{"role": "user", "content": message}]
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"Error prompting LLM: {str(e)}")
        raise
