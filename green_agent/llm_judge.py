"""
LLM-as-Judge Evaluation Module

Provides fallback evaluation using vision LLMs when rule-based evaluation fails.
This helps catch false negatives where the agent succeeded but programmatic checks failed.
"""

import base64
import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class EvaluationEvidence:
    """Evidence collected for LLM evaluation."""
    task_instruction: str
    screenshot_before: Optional[bytes] = None  # PNG bytes
    screenshot_after: Optional[bytes] = None   # PNG bytes
    action_sequence: List[str] = field(default_factory=list)
    action_details: List[Dict[str, Any]] = field(default_factory=list)
    agent_reasoning: Optional[str] = None
    rule_based_score: float = 0.0
    rule_based_error: Optional[str] = None


# Prompt template for LLM judge
LLM_JUDGE_SYSTEM_PROMPT = """You are an expert evaluator for desktop automation tasks. Your job is to determine whether an AI agent successfully completed a given task by analyzing screenshots and action logs.

Be objective and focus on whether the GOAL was achieved, not whether the agent took the optimal path. Minor inefficiencies or extra actions should not affect your judgment if the end result is correct."""

LLM_JUDGE_USER_PROMPT = """## Task to Evaluate
{task_instruction}

## Agent's Actions
{action_sequence}

## Agent's Final Response
{agent_reasoning}

## Rule-Based Evaluation Result
The programmatic evaluation returned a score of {rule_based_score}. This may be a false negative.
{rule_based_error}

## Your Task
Analyze the BEFORE and AFTER screenshots along with the action sequence to determine if the task was successfully completed.

Consider:
1. Does the AFTER screenshot show the expected end state?
2. Did the agent's actions logically lead to task completion?
3. Could the rule-based evaluation have failed due to timing, minor UI differences, or overly strict matching?

Respond with ONLY a JSON object in this exact format:
```json
{{
  "success": true or false,
  "confidence": 0.0 to 1.0,
  "reasoning": "Your detailed explanation",
  "evidence_used": ["screenshot_before", "screenshot_after", "action_sequence"]
}}
```"""


def _encode_image_for_api(image_bytes: bytes) -> str:
    """Encode image bytes to base64 for API consumption."""
    return base64.b64encode(image_bytes).decode('utf-8')


def _build_prompt_messages(evidence: EvaluationEvidence) -> List[Dict[str, Any]]:
    """Build the messages array for the LLM API call."""

    # Format action sequence
    if evidence.action_sequence:
        action_str = "\n".join(f"{i+1}. {action}" for i, action in enumerate(evidence.action_sequence))
    else:
        action_str = "No actions recorded"

    # Format agent reasoning
    reasoning_str = evidence.agent_reasoning or "No reasoning provided"

    # Format rule-based error
    error_str = f"\nPossible reason for failure: {evidence.rule_based_error}" if evidence.rule_based_error else ""

    # Build user prompt
    user_text = LLM_JUDGE_USER_PROMPT.format(
        task_instruction=evidence.task_instruction,
        action_sequence=action_str,
        agent_reasoning=reasoning_str,
        rule_based_score=evidence.rule_based_score,
        rule_based_error=error_str
    )

    # Build content array with images
    content = []

    # Add "BEFORE" screenshot
    if evidence.screenshot_before:
        content.append({"type": "text", "text": "BEFORE screenshot (initial state):"})
        content.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/png;base64,{_encode_image_for_api(evidence.screenshot_before)}",
                "detail": "low"  # Use low detail to reduce costs
            }
        })

    # Add "AFTER" screenshot
    if evidence.screenshot_after:
        content.append({"type": "text", "text": "AFTER screenshot (final state):"})
        content.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/png;base64,{_encode_image_for_api(evidence.screenshot_after)}",
                "detail": "low"
            }
        })

    # Add the main prompt text
    content.append({"type": "text", "text": user_text})

    return [
        {"role": "system", "content": LLM_JUDGE_SYSTEM_PROMPT},
        {"role": "user", "content": content}
    ]


def _parse_llm_response(response_text: str) -> Dict[str, Any]:
    """Parse the LLM's JSON response."""

    # Try to extract JSON from the response
    text = response_text.strip()

    # Handle markdown code blocks
    if "```json" in text:
        start = text.find("```json") + 7
        end = text.find("```", start)
        if end > start:
            text = text[start:end].strip()
    elif "```" in text:
        start = text.find("```") + 3
        end = text.find("```", start)
        if end > start:
            text = text[start:end].strip()

    try:
        result = json.loads(text)

        # Validate required fields
        if "success" not in result:
            result["success"] = False
        if "confidence" not in result:
            result["confidence"] = 0.5
        if "reasoning" not in result:
            result["reasoning"] = "No reasoning provided"
        if "evidence_used" not in result:
            result["evidence_used"] = []

        # Ensure types are correct
        result["success"] = bool(result["success"])
        result["confidence"] = float(result["confidence"])
        result["confidence"] = max(0.0, min(1.0, result["confidence"]))

        return result

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM response as JSON: {e}")
        logger.error(f"Response text: {text[:500]}")
        return {
            "success": False,
            "confidence": 0.0,
            "reasoning": f"Failed to parse LLM response: {str(e)}",
            "evidence_used": [],
            "parse_error": True
        }


async def llm_judge_evaluation_openai(
    evidence: EvaluationEvidence,
    model: str = "gpt-4o",
    api_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Use OpenAI's vision model to evaluate task success.

    Args:
        evidence: Collected evaluation evidence
        model: OpenAI model to use (gpt-4o, gpt-4o-mini, etc.)
        api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)

    Returns:
        Dict with success, confidence, reasoning, and metadata
    """
    try:
        import openai
    except ImportError:
        logger.error("openai package not installed")
        return {
            "success": False,
            "confidence": 0.0,
            "reasoning": "OpenAI package not installed",
            "error": "missing_dependency"
        }

    api_key = api_key or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        logger.error("No OpenAI API key provided")
        return {
            "success": False,
            "confidence": 0.0,
            "reasoning": "No OpenAI API key available",
            "error": "missing_api_key"
        }

    client = openai.AsyncOpenAI(api_key=api_key)
    messages = _build_prompt_messages(evidence)

    try:
        logger.info(f"Calling OpenAI {model} for LLM judge evaluation")

        response = await client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=500,
            temperature=0.1  # Low temperature for consistent judgments
        )

        response_text = response.choices[0].message.content
        logger.info(f"LLM judge response: {response_text[:200]}...")

        result = _parse_llm_response(response_text)
        result["model"] = model
        result["provider"] = "openai"

        return result

    except Exception as e:
        logger.error(f"OpenAI API call failed: {e}")
        return {
            "success": False,
            "confidence": 0.0,
            "reasoning": f"API call failed: {str(e)}",
            "error": str(e)
        }


async def llm_judge_evaluation_anthropic(
    evidence: EvaluationEvidence,
    model: str = "claude-sonnet-4-20250514",
    api_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Use Anthropic's Claude model to evaluate task success.

    Args:
        evidence: Collected evaluation evidence
        model: Anthropic model to use
        api_key: Anthropic API key (defaults to ANTHROPIC_API_KEY env var)

    Returns:
        Dict with success, confidence, reasoning, and metadata
    """
    try:
        import anthropic
    except ImportError:
        logger.error("anthropic package not installed")
        return {
            "success": False,
            "confidence": 0.0,
            "reasoning": "Anthropic package not installed",
            "error": "missing_dependency"
        }

    api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        logger.error("No Anthropic API key provided")
        return {
            "success": False,
            "confidence": 0.0,
            "reasoning": "No Anthropic API key available",
            "error": "missing_api_key"
        }

    client = anthropic.AsyncAnthropic(api_key=api_key)

    # Build content for Anthropic's format
    content = []

    # Format action sequence
    if evidence.action_sequence:
        action_str = "\n".join(f"{i+1}. {action}" for i, action in enumerate(evidence.action_sequence))
    else:
        action_str = "No actions recorded"

    reasoning_str = evidence.agent_reasoning or "No reasoning provided"
    error_str = f"\nPossible reason for failure: {evidence.rule_based_error}" if evidence.rule_based_error else ""

    # Add before screenshot
    if evidence.screenshot_before:
        content.append({"type": "text", "text": "BEFORE screenshot (initial state):"})
        content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/png",
                "data": _encode_image_for_api(evidence.screenshot_before)
            }
        })

    # Add after screenshot
    if evidence.screenshot_after:
        content.append({"type": "text", "text": "AFTER screenshot (final state):"})
        content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/png",
                "data": _encode_image_for_api(evidence.screenshot_after)
            }
        })

    # Add main prompt
    user_text = LLM_JUDGE_USER_PROMPT.format(
        task_instruction=evidence.task_instruction,
        action_sequence=action_str,
        agent_reasoning=reasoning_str,
        rule_based_score=evidence.rule_based_score,
        rule_based_error=error_str
    )
    content.append({"type": "text", "text": user_text})

    try:
        logger.info(f"Calling Anthropic {model} for LLM judge evaluation")

        response = await client.messages.create(
            model=model,
            max_tokens=500,
            system=LLM_JUDGE_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": content}]
        )

        response_text = response.content[0].text
        logger.info(f"LLM judge response: {response_text[:200]}...")

        result = _parse_llm_response(response_text)
        result["model"] = model
        result["provider"] = "anthropic"

        return result

    except Exception as e:
        logger.error(f"Anthropic API call failed: {e}")
        return {
            "success": False,
            "confidence": 0.0,
            "reasoning": f"API call failed: {str(e)}",
            "error": str(e)
        }


async def llm_judge_evaluation(
    evidence: EvaluationEvidence,
    provider: str = "openai",
    model: Optional[str] = None,
    confidence_threshold: float = 0.7
) -> Dict[str, Any]:
    """
    Main entry point for LLM-based evaluation.

    Args:
        evidence: Collected evaluation evidence
        provider: LLM provider ("openai" or "anthropic")
        model: Model name (defaults to provider's best vision model)
        confidence_threshold: Minimum confidence to consider judgment valid

    Returns:
        Dict with:
            - success: bool
            - score: float (0.0 or 1.0)
            - confidence: float
            - reasoning: str
            - meets_threshold: bool
            - method: str
    """
    # Set default models
    if model is None:
        model = "gpt-4o" if provider == "openai" else "claude-sonnet-4-20250514"

    # Call appropriate provider
    if provider == "openai":
        result = await llm_judge_evaluation_openai(evidence, model)
    elif provider == "anthropic":
        result = await llm_judge_evaluation_anthropic(evidence, model)
    else:
        return {
            "success": False,
            "score": 0.0,
            "confidence": 0.0,
            "reasoning": f"Unknown provider: {provider}",
            "meets_threshold": False,
            "method": "llm_judge_error"
        }

    # Add score and threshold check
    result["score"] = 1.0 if result["success"] else 0.0
    result["meets_threshold"] = result["confidence"] >= confidence_threshold
    result["method"] = "llm_judge"
    result["confidence_threshold"] = confidence_threshold

    return result
