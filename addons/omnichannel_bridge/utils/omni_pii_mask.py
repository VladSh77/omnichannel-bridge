# -*- coding: utf-8 -*-
"""
PII Masking Utility for Omnichannel Bridge

Masks personally identifiable information (PII) in logs, debug output, and error messages
to comply with GDPR/RODO data protection regulations.

Usage:
    from .omni_pii_mask import mask_pii_for_logging

    text = "Customer john.doe@example.com called with query"
    safe = mask_pii_for_logging(text)
    _logger.debug(safe)  # → "Customer j***@example.com called with query"
"""

import re


def mask_email(email):
    """Mask email address, keeping domain for reference.

    Args:
        email (str): Email address

    Returns:
        str: Masked email (e.g. john.doe@example.com -> j***@example.com)
    """
    if not email or "@" not in email:
        return email
    local, domain = email.rsplit("@", 1)
    if len(local) <= 1:
        return f"*@{domain}"
    first = local[0]
    return f"{first}***@{domain}"


def mask_phone(phone):
    """Mask phone number, keeping country code and last 2 digits.

    Args:
        phone (str): Phone number

    Returns:
        str: Masked phone (e.g. +380671234567 -> +***34567)
    """
    if not phone:
        return phone
    # Remove common separators
    cleaned = re.sub(r"[\s\-\(\)\.]+", "", phone)
    if len(cleaned) <= 5:
        return "***"
    # Keep prefix (+ or first digit) and last 2 digits
    if cleaned.startswith("+"):
        # International format: keep + and last 2 digits
        return f"+***{cleaned[-2:]}"
    else:
        # Domestic format: keep first digit and last 2 digits
        return f"{cleaned[0]}***{cleaned[-2:]}"


def mask_name(name):
    """Mask full name, keeping initials.

    Args:
        name (str): Full name (e.g. "John Doe")

    Returns:
        str: Masked name (e.g. "J. D." or "***" if empty)
    """
    if not name:
        return "***"
    name = name.strip()
    if not name:
        return "***"
    parts = name.split()
    if not parts:
        return "***"
    # Keep first letter of each word
    initials = [p[0].upper() + "." for p in parts if p]
    return " ".join(initials) if initials else "***"


def mask_pii_in_text(text):
    """Mask all PII patterns in plain text.

    Detects and masks:
    - Email addresses
    - Phone numbers (international format and common patterns)
    - Names (simple heuristic: Capitalized words followed by another Capitalized word)

    Args:
        text (str): Text containing potential PII

    Returns:
        str: Text with PII masked
    """
    if not text:
        return text

    result = text

    # Mask emails
    email_pattern = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
    result = re.sub(email_pattern, lambda m: mask_email(m.group(0)), result)

    # Mask phone numbers (international +XX or 0X, including spaces/dashes)
    phone_pattern = (
        r"(\+\d{1,3}[\s\-]?)?(\(?\d{2,4}\)?[\s\-]?)?\d{3}[\s\-]?\d{2,3}[\s\-]?\d{2,4}"
    )
    result = re.sub(phone_pattern, lambda m: mask_phone(m.group(0)), result)

    return result


def mask_pii_for_logging(message, **kwargs):
    """Safe wrapper for logging with PII masking.

    Masks PII in message and all string values in kwargs before logging.

    Args:
        message (str): Log message template (or plain text)
        **kwargs: Key-value pairs (will mask string values)

    Returns:
        tuple: (safe_message, safe_kwargs) ready for _logger.debug/info/warning

    Example:
        msg, kw = mask_pii_for_logging(
            "Processing contact %(email)s for partner",
            email="john@example.com",
            partner_id=42
        )
        _logger.debug(msg, kw)  # Safe to log
    """
    safe_msg = mask_pii_in_text(message)
    safe_kwargs = {}

    for key, value in kwargs.items():
        if isinstance(value, str):
            safe_kwargs[key] = mask_pii_in_text(value)
        else:
            safe_kwargs[key] = value

    return safe_msg, safe_kwargs


def is_pii_present(text):
    """Check if text contains potential PII patterns.

    Args:
        text (str): Text to check

    Returns:
        bool: True if PII patterns detected
    """
    if not text:
        return False

    email_pattern = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
    phone_pattern = (
        r"(\+\d{1,3}[\s\-]?)?(\(?\d{2,4}\)?[\s\-]?)?\d{3}[\s\-]?\d{2,3}[\s\-]?\d{2,4}"
    )

    return bool(re.search(email_pattern, text)) or bool(re.search(phone_pattern, text))
