"""
Lightweight scanner that blocks obvious patient-identifying information (PHI)
from free-text fields on the student Patient Care Report narrative.

This is a best-effort guardrail, not a substitute for training — the form UI
teaches students to write de-identified narratives (age/sex/complaint only,
no names/dates/contact info), and this scan catches the common, detectable
mistakes (SSNs, phone numbers, emails, street addresses, MRNs, explicit
dates, salutations) before the report is saved.
"""
import re

_SSN_RE = re.compile(r'\b\d{3}[-\s]\d{2}[-\s]\d{4}\b')
_PHONE_RE = re.compile(
    r'(\(\d{3}\)\s*\d{3}[-.\s]?\d{4})|(\b\d{3}[-.\s]\d{3}[-.\s]\d{4}\b)|(\b\d{10,11}\b)'
)
_EMAIL_RE = re.compile(r'\b[\w.+-]+@[\w-]+\.[A-Za-z]{2,}\b')
_ZIP_RE = re.compile(r'\b\d{5}(?:-\d{4})?\b')
_STREET_RE = re.compile(
    r'\b\d{1,6}\s+\w+(?:\s\w+){0,3}\s+'
    r'(street|st|avenue|ave|road|rd|boulevard|blvd|drive|dr|lane|ln|court|ct|way|place|pl|circle|cir|highway|hwy)\b',
    re.IGNORECASE,
)
_DATE_RE = re.compile(
    r'\b\d{1,2}/\d{1,2}/\d{2,4}\b|'
    r'\b(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|'
    r'aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+\d{1,2}(?:st|nd|rd|th)?,?\s+\d{4}\b',
    re.IGNORECASE,
)
_SALUTATION_RE = re.compile(r'\b(mr|mrs|ms|miss|mister)\.?\s+[A-Z][a-z]+\b', re.IGNORECASE)
_KEYWORD_RE = re.compile(
    r'\b(dob|date of birth|ssn|social security|mrn|medical record( number)?|'
    r'chart\s*#|patient(\'s)?\s+name|insurance\s+(id|number|policy)|policy\s+number|'
    r'driver\'?s?\s+license|passport\s+(number|no\.?)?)\b',
    re.IGNORECASE,
)

_CHECKS = [
    ('Social Security number', _SSN_RE),
    ('phone number', _PHONE_RE),
    ('email address', _EMAIL_RE),
    ('street address', _STREET_RE),
    ('specific date (birthdate or similar)', _DATE_RE),
    ('name-style salutation (e.g. "Mr. Smith")', _SALUTATION_RE),
    ('identifying reference (DOB, MRN, SSN, policy #, etc.)', _KEYWORD_RE),
    ('ZIP code or ID-style number', _ZIP_RE),
]


def scan_for_phi(text):
    """Return a list of human-readable violation messages found in `text`, or [] if clean."""
    if not text:
        return []
    found = []
    for label, pattern in _CHECKS:
        if pattern.search(text):
            found.append(f'This looks like it may contain a {label}. Remove any patient-identifying details.')
    return found
