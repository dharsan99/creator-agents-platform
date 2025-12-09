"""LLM service for generating creator profile documentation."""
import json
import logging
from typing import Dict, Any

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from app.config import settings

logger = logging.getLogger(__name__)


class CreatorProfileLLMService:
    """Service for generating LLM-optimized creator profiles."""

    def __init__(self):
        self.llm = ChatOpenAI(
            model=settings.openai_model,
            api_key=settings.openai_api_key,
            temperature=1.0,  # gpt-5-nano only supports temperature=1
        )

    def generate_profile_document(self, raw_data: dict) -> Dict[str, Any]:
        """Generate comprehensive profile document from raw creator data.

        Args:
            raw_data: Raw data from Topmate API

        Returns:
            Dictionary with:
                - llm_summary: Comprehensive summary for LLM context
                - sales_pitch: Optimized pitch for selling services
                - target_audience_description: Who should buy
                - value_propositions: List of key value props
                - services: Structured service data
                - agent_instructions: How agents should sell
                - objection_handling: Common objections and responses
        """
        logger.info("Generating LLM profile document...")

        system_prompt = """You are an expert at analyzing creator profiles and generating sales-optimized documentation for AI agents.

Your task is to analyze raw creator data and generate comprehensive documentation that AI agents will use to sell the creator's services.

The documentation should be:
1. Factual and based only on provided data
2. Optimized for AI agents to understand and use
3. Focused on helping convert leads into customers
4. Include social proof, credibility markers, and value propositions
5. Anticipate and address common objections

Return your response as a valid JSON object with these fields:
- llm_summary: A comprehensive 3-4 paragraph summary of who the creator is, their expertise, track record, and what they offer. This is what AI agents will read to understand the creator.
- sales_pitch: A compelling 2-3 paragraph pitch that agents can adapt when reaching out to leads. Focus on transformation and outcomes.
- target_audience_description: Detailed description of ideal customers - their roles, pain points, goals, and why this service is perfect for them.
- value_propositions: Array of 5-7 specific value propositions that make this offering unique and valuable.
- services: Array of service objects, each with: name, type, pricing, schedule, description, current_enrollment
- agent_instructions: Specific instructions for AI agents on how to sell this service - tone, approach, what to emphasize, when to send payment links.
- objection_handling: Object with common objections as keys and suggested responses as values.

Be specific, use numbers and social proof, and make it easy for AI agents to convert leads."""

        user_prompt = f"""Analyze this creator's data and generate the sales documentation:

{json.dumps(raw_data, indent=2)}

Generate comprehensive documentation that AI sales agents will use to sell this creator's services."""

        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]

            response = self.llm.invoke(messages)
            content = response.content

            # Parse JSON from response
            # Handle markdown code blocks if present
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            # Clean control characters from JSON
            import re
            # Remove control characters except newlines, tabs, and carriage returns
            content = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', content)

            # Remove trailing commas before closing brackets/braces
            content = re.sub(r',(\s*[}\]])', r'\1', content)

            # Use strict=False to allow control characters in strings
            result = json.loads(content, strict=False)

            # Post-process: convert arrays to strings for expected string fields
            string_fields = ["llm_summary", "sales_pitch", "target_audience_description", "agent_instructions"]
            for field in string_fields:
                if field in result and isinstance(result[field], list):
                    result[field] = "\n\n".join(result[field])

            logger.info("Successfully generated profile document")
            return result

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            logger.error(f"LLM response was: {content}")
            raise ValueError(f"LLM returned invalid JSON: {e}")

        except Exception as e:
            logger.error(f"Error generating profile document: {e}")
            raise

    def generate_objection_responses(
        self,
        service_name: str,
        price: int,
        common_objections: list[str]
    ) -> Dict[str, str]:
        """Generate responses to common sales objections.

        Args:
            service_name: Name of the service
            price: Price in rupees/dollars
            common_objections: List of common objections

        Returns:
            Dictionary mapping objections to responses
        """
        prompt = f"""Generate concise, effective responses to these objections for selling {service_name} (priced at ₹{price}):

Objections:
{json.dumps(common_objections, indent=2)}

For each objection, provide a 2-3 sentence response that:
1. Acknowledges the concern
2. Reframes it positively
3. Provides social proof or specific value

Return as JSON object with objection text as keys and response as values."""

        try:
            response = self.llm.invoke([HumanMessage(content=prompt)])
            content = response.content

            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()

            return json.loads(content)

        except Exception as e:
            logger.error(f"Error generating objection responses: {e}")
            return {}
