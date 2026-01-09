import time
from typing import Generator, Optional

from src.config import settings
from src.logger import get_logger
from src.utils.clients import get_openai_client, get_openrouter_client
from .prompt_modifier import PromptModifier

logger = get_logger(__name__)

class ResponseGenerator:
    def __init__(self):
        if settings.model_provider == "openrouter":
            self.provider = "openrouter"
            self.client = get_openrouter_client()
        else:
            self.provider = "openai"
            self.client = get_openai_client()
        self.model = settings.analysis_model

    def generate_response(self, user_query: str, context: str, user_name: str = "Trader", current_date: Optional[str] = None, date_period_context: Optional[str] = None, is_followup: bool = False, trade_scope: Optional[list] = None) -> str:
        """
        Generates a response using the configured LLM provider (non-streaming).
        """
        start_time = time.perf_counter()
        from src.api.helpers import InputSanitizer
        sanitized_user_query = InputSanitizer.sanitize_user_input(user_query)
        query_preview = sanitized_user_query[:50] + "..." if len(sanitized_user_query) > 50 else sanitized_user_query
        context_size = len(context)
        
        logger.info(f"[LLM] Starting response generation | provider={self.provider} | model={self.model} | is_followup={is_followup} | query='{query_preview}'")
        logger.debug(f"[LLM] Context size: {context_size} chars")

        formatted_system_prompt = PromptModifier.get_modified_prompt(
            user_name=user_name,
            current_date=current_date or "",
            date_period_context=date_period_context or ""
        )
        
        # Inject scope constraint for follow-ups
        followup_constraint = ""
        if is_followup and trade_scope:
            trade_ids_str = ", ".join(str(tid) for tid in trade_scope)
            followup_constraint = f"""
[SCOPE CONSTRAINT - THIS IS A FOLLOW-UP QUESTION]
Analyze ONLY the trades from the previous query: [{trade_ids_str}]
Do NOT fetch or analyze other trades. Stay focused on these specific trades and their details.
Previous context: {len(trade_scope)} trades in scope
[END SCOPE]

"""
            logger.info(f"[LLM] Follow-up scope constraint applied | trade_ids={trade_ids_str[:50]}...")

        try:
            api_start = time.perf_counter()
            if self.provider == "openrouter":
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": formatted_system_prompt},
                        {"role": "user", "content": f"{followup_constraint}Context:\n{context}\n\nUser Query:\n{sanitized_user_query}"}
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
                        {"role": "user", "content": f"Context:\n{context}\n\nUser Query:\n{sanitized_user_query}"}
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

            from src.llm.output_validator import OutputValidator
            sanitized_content = OutputValidator.sanitize_output(content)
            return sanitized_content

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
        date_period_context: Optional[str] = None,
        is_followup: bool = False,
        trade_scope: Optional[list] = None
    ) -> Generator[str, None, None]:
        """
        Generates a streaming response using the configured LLM provider.
        Yields text chunks as they arrive from the API.
        """
        start_time = time.perf_counter()
        query_preview = user_query[:50] + "..." if len(user_query) > 50 else user_query
        context_size = len(context)
        
        logger.info(f"[LLM_STREAM] Starting streaming response | provider={self.provider} | model={self.model} | is_followup={is_followup} | query='{query_preview}'")
        logger.debug(f"[LLM_STREAM] Context size: {context_size} chars")

        formatted_system_prompt = PromptModifier.get_modified_prompt(
            user_name=user_name,
            current_date=current_date or "",
            date_period_context=date_period_context or ""
        )
        
        # Inject scope constraint for follow-ups
        followup_constraint = ""
        if is_followup and trade_scope:
            trade_ids_str = ", ".join(str(tid) for tid in trade_scope)
            followup_constraint = f"""
[SCOPE CONSTRAINT - THIS IS A FOLLOW-UP QUESTION]
Analyze ONLY the trades from the previous query: [{trade_ids_str}]
Do NOT fetch or analyze other trades. Stay focused on these specific trades and their details.
Previous context: {len(trade_scope)} trades in scope
[END SCOPE]

"""
            logger.info(f"[LLM_STREAM] Follow-up scope constraint applied | trade_ids={trade_ids_str[:50]}...")
        
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
                        {"role": "user", "content": f"{followup_constraint}Context:\n{context}\n\nUser Query:\n{user_query}"}
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