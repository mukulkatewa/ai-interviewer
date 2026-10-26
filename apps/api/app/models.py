from pydantic import BaseModel, ConfigDict


class ApiModel(BaseModel):
    """Base for models that appear in API responses.

    A field with a default (e.g. `skills: list = []`) is always present in our
    JSON output, so mark it required in the *response* schema. Without this,
    the generated TypeScript types say `skills?: string[]` and every client
    must guard against a value that is never missing (projectprep.md, D21).
    """

    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
