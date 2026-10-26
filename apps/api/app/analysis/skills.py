"""Skill-name normalization: decide when two spellings mean the same skill.

`skill_key("React.js") == skill_key("reactjs") == skill_key("React")`. Keys are
only for comparison; we always show the user the original spelling.
"""

import re
from collections.abc import Iterable

# Characters people use interchangeably inside skill names ("Node.js", "CI/CD", "scikit-learn").
_SEPARATORS = re.compile(r"[\s.\-_/]+")
# Word tokens for scanning free text. "+" and "#" stay so "C++" and "C#" survive.
_TOKENS = re.compile(r"[a-z0-9+#]+")
# Longest skill phrase we look for in free text ("google cloud platform").
_MAX_NGRAM = 3

# Spelling -> canonical key. Keys on the left are already separator-free lowercase.
# Kept explicit on purpose: generic rules (e.g. stripping a trailing "s") break
# real names like "Redis" and "AWS".
ALIASES: dict[str, str] = {
    "js": "javascript",
    "ts": "typescript",
    "reactjs": "react",
    "node": "nodejs",
    "vuejs": "vue",
    "expressjs": "express",
    "nestjs": "nest",
    "golang": "go",
    "postgres": "postgresql",
    "psql": "postgresql",
    "mongo": "mongodb",
    "k8s": "kubernetes",
    "amazonwebservices": "aws",
    "googlecloud": "gcp",
    "googlecloudplatform": "gcp",
    "msazure": "azure",
    "microsoftazure": "azure",
    "rest": "restapi",
    "restapis": "restapi",
    "restful": "restapi",
    "restfulapi": "restapi",
    "restfulapis": "restapi",
    "microservice": "microservices",
    "ml": "machinelearning",
    "llms": "llm",
    "sklearn": "scikitlearn",
    "tf": "tensorflow",
    "springboot": "spring",
}

# Names that are also common English words or single letters. They count when a
# candidate *lists* them as a skill, but finding "go" in "go-to-market" proves nothing.
AMBIGUOUS_IN_TEXT = frozenset({"go", "r", "c", "spring", "swift"})


def _prepare(text: str) -> str:
    # ".net" would otherwise lose its dot and collide with the word "net".
    return text.lower().replace(".net", "dotnet")


def skill_key(name: str) -> str:
    key = _SEPARATORS.sub("", _prepare(name))
    return ALIASES.get(key, key)


def keys_in_text(texts: Iterable[str]) -> set[str]:
    """Skill keys for every 1..3-word phrase in `texts`.

    Joining n-grams the same way skill_key strips separators means "Node.js"
    (tokens "node", "js") and "REST APIs" ("rest", "apis") are found in prose.
    """
    found: set[str] = set()
    for text in texts:
        tokens = _TOKENS.findall(_prepare(text))
        for n in range(1, _MAX_NGRAM + 1):
            for i in range(len(tokens) - n + 1):
                key = "".join(tokens[i : i + n])
                found.add(ALIASES.get(key, key))
    return found - AMBIGUOUS_IN_TEXT
