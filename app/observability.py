"""LangSmith tracing, with personal data removed before anything leaves the server.

Tracing is switched on from .env (LANGSMITH_TRACING=true plus LANGSMITH_API_KEY). We build the
tracer ourselves, instead of letting environment variables switch tracing on globally, because we
must attach the anonymizer to it: that is how emails, tokens and keys are redacted."""
import logging
import re

logger = logging.getLogger(__name__)

EMAIL = r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"
JWT = r"eyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}"
GOOGLE_API_KEY = r"AIza[0-9A-Za-z_\-]{30,}"

REDACTIONS = [
    {"pattern": EMAIL, "replace": "<email>"},
    {"pattern": JWT, "replace": "<jwt>"},
    {"pattern": GOOGLE_API_KEY, "replace": "<api-key>"},
]


def redact(text: str) -> str:
    """The same rules in plain Python, so they can be tested without LangSmith."""
    for rule in REDACTIONS:
        text = re.sub(rule["pattern"], rule["replace"], text)
    return text


def build_tracer(settings):
    """Returns a LangChain tracer that sends redacted traces to LangSmith, or None when tracing is off."""
    if not settings.langsmith_tracing:
        return None
    if not settings.langsmith_api_key:
        logger.warning("LANGSMITH_TRACING is on but LANGSMITH_API_KEY is empty: tracing stays off")
        return None
    from langchain_core.tracers.langchain import LangChainTracer
    from langsmith import Client
    from langsmith.anonymizer import create_anonymizer

    client = Client(api_key=settings.langsmith_api_key, anonymizer=create_anonymizer(REDACTIONS))
    return LangChainTracer(client=client, project_name=settings.langsmith_project)
