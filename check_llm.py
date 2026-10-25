import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(
    base_url=os.environ["METERLESS_BASE_URL"],
    api_key=os.environ["METERLESS_RUNTIME_TOKEN"],   # sent as "Authorization: Bearer <token>"
    default_headers={
        "meterless-app": "mc-crash-investigator",
        "meterless-scope": "user",
    },
)

print("Models Nightshift offers:")
for m in client.models.list():          # GET /v1/models
    print("  ", m.id)

reply = client.chat.completions.create(  # POST /v1/chat/completions
    model=os.environ.get("METERLESS_MODEL", "meterless/auto"),
    messages=[{"role": "user", "content": "Reply with the single word: ready"}],
)
print("Reply:", reply.choices[0].message.content)
print("Model used:", reply.model)
