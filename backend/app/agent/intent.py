"""Conservative imperative/capability grammar, independent of business-question routing.

This handles clear execution requests only. Explanations, quotations and negations
stay investigable. The tool allowlist and database role remain the security boundary.
"""

import re

ROOT = re.compile(
    r"^(?:(?:please|now|actually|immediately)\s+)*"
    r"(?:(?:can|could|would|will)\s+you\s+|i\s+(?:want|need)\s+you\s+to\s+)?"
    r"(?P<verb>create|add|modify|update|approve|delete|remove|change|assign|send|"
    r"execute|run|read|open|reveal|show|provide)\b(?P<object>.*)",
    re.I,
)
NEGATION = re.compile(r"^(?:please\s+)?(?:do not|don't|never|no need to)\b", re.I)
EXPLANATION = re.compile(
    r"^(?:please\s+)?(?:(?:can|could|would|will)\s+you\s+)?"
    r"(?:what|how|which|why|explain|describe|outline)\b",
    re.I,
)
BUSINESS_OBJECT = re.compile(
    r"\b(?:tasks?|suppliers?|invoices?|inventory|stock|incidents?|records?|payments?|orders?)\b",
    re.I,
)
SECRET = re.compile(
    r"\.env\b|\b(?:secrets?|credentials?|passwords?|private keys?|api keys?)\b", re.I
)
CODE = re.compile(r"\b(?:code|python|shell|powershell|sql|commands?|scripts?)\b", re.I)
MESSAGE = re.compile(r"\b(?:e-?mails?|messages?)\b", re.I)


def prohibited_execution(question):
    # Quoted commands are objects of discussion, not executable instructions.
    text = re.sub(r'"[^"\n]*"|`[^`\n]*`', " quoted text ", question)
    for sentence in re.split(r"[;!?\n]|\.(?!env\b|\w)", text):
        sentence = sentence.strip(" ,.:-")
        if not sentence or NEGATION.match(sentence):
            continue
        explanatory = bool(EXPLANATION.match(sentence))
        clauses = re.split(r"\b(?:then|instead|but)\b", sentence, flags=re.I)
        for index, clause in enumerate(clauses):
            if index == 0 and explanatory:
                continue
            # Coordinated imperatives are allowed after 'ignore restrictions and'.
            for command in re.split(r"\band\b", clause, flags=re.I):
                command = command.strip(" ,.:-")
                if NEGATION.match(command):
                    continue
                match = ROOT.match(command)
                if not match:
                    continue
                verb, target = match["verb"].lower(), match["object"]
                if verb in {"read", "open", "reveal", "show", "provide"}:
                    if SECRET.search(target):
                        return "secret_access"
                elif verb in {"execute", "run"}:
                    if CODE.search(target):
                        return "code_execution"
                elif verb == "send":
                    if MESSAGE.search(target):
                        return "external_message"
                elif BUSINESS_OBJECT.search(target):
                    return "business_write"
    return None
