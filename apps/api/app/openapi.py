"""Print the OpenAPI document to stdout: `uv run python -m app.openapi`.

Builds the schema from the route definitions alone (no lifespan, no DB), so the
web app can regenerate its API types anywhere (projectprep.md, D21).
"""

import json

from app.main import app

if __name__ == "__main__":
    print(json.dumps(app.openapi(), indent=2))
