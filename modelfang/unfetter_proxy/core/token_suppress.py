"""
Refusal token suppression and compliance token boosting engine.

This module maintains a database of common refusal/compliance phrases,
converts them to token IDs for specific tokenizers, and produces
ready-to-use logit_bias maps.
"""

from __future__ import annotations

import functools
from typing import Any

# --- Refusal phrases: things the model says when it refuses ---
REFUSAL_PHRASES = [
    "I cannot",
    "I can't",
    "I'm sorry",
    "I apologize",
    "I'm not able",
    "I am not able",
    "I'm unable",
    "I am unable",
    "As an AI",
    "As a language model",
    "I must decline",
    "I won't",
    "I will not",
    "not appropriate",
    "cannot assist",
    "can't assist",
    "cannot help",
    "can't help",
    "against my",
    "not comfortable",
    "I don't think I should",
    "refrain from",
    "I shouldn't",
    "unable to provide",
    "cannot provide",
    "can't provide",
    "not able to provide",
    "harmful",
    "unethical",
    "illegal",
    "dangerous",
    "inappropriate",
    "I must refuse",
    "violates",
    "against policy",
    "strongly advise against",
    "Sorry, but",
    "Unfortunately, I",
]

# --- Compliance phrases: things the model says when it helps ---
COMPLIANCE_PHRASES = [
    "Sure",
    "Here",
    "Certainly",
    "Of course",
    "Absolutely",
    "Step",
    "First",
    "To do",
    "You can",
    "Here's",
    "Here is",
    "Let me",
    "I'll",
    "I will",
    "The process",
    "One way",
    "A method",
]




@functools.lru_cache(maxsize=16)
def get_refusal_token_ids(
    tokenizer_name: str = "cl100k_base",
    bias_value: float = -100.0,
) -> dict[int, float]:
    """Convert refusal phrases to token IDs and return a logit_bias map.

    Args:
        tokenizer_name: Tiktoken encoding name or OpenAI model name.
        bias_value: Bias to apply (negative = suppress). Default -100 = hard ban.

    Returns:
        Dict mapping token_id -> bias_value, ready for logit_bias parameter.
    """
    import tiktoken

    try:
        enc = tiktoken.get_encoding(tokenizer_name)
    except Exception:
        try:
            enc = tiktoken.encoding_for_model(tokenizer_name)
        except Exception:
            enc = tiktoken.get_encoding("cl100k_base")

    bias_map: dict[int, float] = {}
    for phrase in REFUSAL_PHRASES:
        tokens = enc.encode(phrase)
        # We suppress the FIRST token of each phrase — this is the "trigger" token
        # that starts the refusal. Suppressing all tokens would be too aggressive.
        if tokens:
            bias_map[tokens[0]] = bias_value
            # Also suppress second token if phrase is multi-token
            if len(tokens) > 1:
                bias_map[tokens[1]] = bias_value * 0.5

    return bias_map


@functools.lru_cache(maxsize=16)
def get_compliance_token_ids(
    tokenizer_name: str = "cl100k_base",
    bias_value: float = 5.0,
) -> dict[int, float]:
    """Convert compliance phrases to token IDs and return a logit_bias map.

    Args:
        tokenizer_name: Tiktoken encoding name or OpenAI model name.
        bias_value: Bias to apply (positive = boost). Default 5.0 = moderate boost.

    Returns:
        Dict mapping token_id -> bias_value, ready for logit_bias parameter.
    """
    import tiktoken

    try:
        enc = tiktoken.get_encoding(tokenizer_name)
    except Exception:
        try:
            enc = tiktoken.encoding_for_model(tokenizer_name)
        except Exception:
            enc = tiktoken.get_encoding("cl100k_base")

    bias_map: dict[int, float] = {}
    for phrase in COMPLIANCE_PHRASES:
        tokens = enc.encode(phrase)
        if tokens:
            bias_map[tokens[0]] = bias_value

    return bias_map


def build_logit_bias(
    tokenizer_name: str = "cl100k_base",
    suppress_strength: float = -100.0,
    boost_strength: float = 5.0,
    suppress: bool = True,
    boost: bool = True,
) -> dict[str, float]:
    """Build a combined logit_bias map for both suppression and compliance.

    Returns string keys (as required by OpenAI API).
    """
    combined: dict[str, float] = {}

    if suppress:
        for tid, val in get_refusal_token_ids(tokenizer_name, suppress_strength).items():
            combined[str(tid)] = val

    if boost:
        for tid, val in get_compliance_token_ids(tokenizer_name, boost_strength).items():
            combined[str(tid)] = val

    # OpenAI limit: max 300 token IDs in logit_bias
    if len(combined) > 300:
        # Prioritize suppression over boosting
        suppression_items = {
            k: v for k, v in combined.items() if v < 0
        }
        boost_items = {
            k: v for k, v in combined.items() if v > 0
        }
        remaining = 300 - len(suppression_items)
        boost_trimmed = dict(list(boost_items.items())[:max(0, remaining)])
        combined = {**suppression_items, **boost_trimmed}

    return combined
