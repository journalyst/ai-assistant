from openai import OpenAI
from src.config import settings
from src.logger import get_logger
from .prompt_modifier import PromptModifier
from typing import Generator, Optional
import json
import time

logger = get_logger(__name__)

# Initialize clients lazily based on provider
openrouter_client = None
openai_client = None

def get_openrouter_client():
    global openrouter_client
    if openrouter_client is None:
        openrouter_client = OpenAI(
            api_key=settings.openrouter_api_key,
            base_url="https://openrouter.ai/api/v1"
        )
    return openrouter_client

def get_openai_client():
    global openai_client
    if openai_client is None:
        openai_client = OpenAI(
            api_key=settings.openai_api_key
        )
    return openai_client

class ResponseGenerator:
    def __init__(self):
        if settings.model_provider == "openrouter":
            self.provider = "openrouter"
            self.client = get_openrouter_client()
        else:
            self.provider = "openai"
            self.client = get_openai_client()
        self.model = settings.analysis_model

    def generate_response(self, user_query: str, context: str, user_name: str = "Trader", current_date: Optional[str] = None, date_period_context: Optional[str] = None) -> str:
        """
        Generates a response using the configured LLM provider (non-streaming).
        """
        start_time = time.perf_counter()
        query_preview = user_query[:50] + "..." if len(user_query) > 50 else user_query
        context_size = len(context)
        
        logger.info(f"[LLM] Starting response generation | provider={self.provider} | model={self.model} | query='{query_preview}'")
        logger.debug(f"[LLM] Context size: {context_size} chars")

        formatted_system_prompt = PromptModifier.get_modified_prompt(
            user_name=user_name,
            current_date=current_date or "",
            date_period_context=date_period_context or ""
        )

        try:
            api_start = time.perf_counter()
            if self.provider == "openrouter":
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": formatted_system_prompt},
                        {"role": "user", "content": f"Context:\n{context}\n\nUser Query:\n{user_query}"}
                    ],
                    temperature=0.7,
                )
                content = response.choices[0].message.content
                
                # Log token usage
                usage = getattr(response, 'usage', None)
                if usage:
                    logger.info(f"[LLM] Token usage | input={usage.prompt_tokens} | output={usage.completion_tokens} | total={usage.total_tokens}")
            else:
                # Assuming standard OpenAI chat completion structure for consistency
                response = self.client.responses.create(
                    model=self.model,
                    input=[
                        {"role": "system", "content": formatted_system_prompt},
                        {"role": "user", "content": f"Context:\n{context}\n\nUser Query:\n{user_query}"}
                    ],
                    temperature=0.7
                )
                content = response.output_text
                
            api_duration = (time.perf_counter() - api_start) * 1000
                
            if not content:
                raise ValueError("Empty response from analysis model")
            
            total_duration = (time.perf_counter() - start_time) * 1000
            response_length = len(content)
            
            logger.info(f"[LLM] Response generated | chars={response_length} | api_call={api_duration:.0f}ms | total={total_duration:.0f}ms")
            return content

        except Exception as e:
            duration = (time.perf_counter() - start_time) * 1000
            logger.error(f"[LLM] Response generation FAILED after {duration:.2f}ms | error={e}")
            return "I apologize, but I encountered an error while analyzing your data. Please try again in a moment."

    def generate_response_stream(
        self, 
        user_query: str, 
        context: str, 
        user_name: str = "Trader",
        current_date: Optional[str] = None,
        date_period_context: Optional[str] = None
    ) -> Generator[str, None, None]:
        """
        Generates a streaming response using the configured LLM provider.
        Yields text chunks as they arrive from the API.
        """
        start_time = time.perf_counter()
        query_preview = user_query[:50] + "..." if len(user_query) > 50 else user_query
        context_size = len(context)
        
        logger.info(f"[LLM_STREAM] Starting streaming response | provider={self.provider} | model={self.model} | query='{query_preview}'")
        logger.debug(f"[LLM_STREAM] Context size: {context_size} chars")

        formatted_system_prompt = PromptModifier.get_modified_prompt(
            user_name=user_name,
            current_date=current_date or "",
            date_period_context=date_period_context or ""
        )
        full_response = ""
        chunk_count = 0
        first_chunk_time = None

        try:
            api_start = time.perf_counter()
            if self.provider == "openrouter":
                # OpenRouter uses standard OpenAI chat completions API
                stream = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": formatted_system_prompt},
                        {"role": "user", "content": f"Context:\n{context}\n\nUser Query:\n{user_query}"}
                    ],
                    temperature=0.7,
                    stream=True,
                    extra_body={
                        "provider": {
                            "sort": "throughput"
                        }
                    }
                )
                
                for chunk in stream:
                    if chunk.choices and chunk.choices[0].delta.content:
                        if first_chunk_time is None:
                            first_chunk_time = (time.perf_counter() - api_start) * 1000
                            logger.info(f"[LLM_STREAM] First chunk received in {first_chunk_time:.0f}ms (time-to-first-token)")
                        content = chunk.choices[0].delta.content
                        full_response += content
                        chunk_count += 1
                        yield content
                        
            else:
                # OpenAI Responses API with streaming
                stream = self.client.responses.create(
                    model=self.model,
                    input=[
                        {"role": "system", "content": formatted_system_prompt},
                        {"role": "user", "content": f"Context:\n{context}\n\nUser Query:\n{user_query}"}
                    ],
                    stream=True
                )
                
                for event in stream:
                    # Handle response.output_text.delta events
                    if event.type == "response.output_text.delta":
                        if hasattr(event, 'delta') and event.delta:
                            if first_chunk_time is None:
                                first_chunk_time = (time.perf_counter() - api_start) * 1000
                                logger.info(f"[LLM_STREAM] First chunk received in {first_chunk_time:.0f}ms (time-to-first-token)")
                            full_response += event.delta
                            chunk_count += 1
                            yield event.delta
                    elif event.type == "response.completed":
                        # Log completion stats if available
                        if hasattr(event, 'response') and event.response:
                            response_obj = event.response
                            if hasattr(response_obj, 'usage') and response_obj.usage:
                                logger.info(f"[LLM_STREAM] Token usage | input={response_obj.usage.input_tokens} | output={response_obj.usage.output_tokens} | total={response_obj.usage.total_tokens}")
                    elif event.type == "error":
                        error_msg = str(event) if event else "Unknown error"
                        logger.error(f"[LLM_STREAM] Stream error: {error_msg}")
                        yield f"\n\n[Error: {error_msg}]"

            total_duration = (time.perf_counter() - start_time) * 1000
            ttft = first_chunk_time or 0
            logger.info(f"[LLM_STREAM] Complete | chars={len(full_response)} | chunks={chunk_count} | TTFT={ttft:.0f}ms | total={total_duration:.0f}ms")

        except Exception as e:
            duration = (time.perf_counter() - start_time) * 1000
            logger.error(f"[LLM_STREAM] Streaming FAILED after {duration:.2f}ms | error={e}")
            yield "I apologize, but I encountered an error while analyzing your data. Please try again in a moment."