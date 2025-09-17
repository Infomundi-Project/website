import json
import base64
from openai import OpenAI

from .custom_exceptions import InfomundiCustomException
from .config import OPENAI_API_KEY


def gpt_summarize(title: str, main_text: str) -> dict:
    """Summarize a news article from the provided URL and structure the response for integration with the JavaScript.

    Returns:
        dict: A dictionary with the structured summary:
            - "addressed_topics": List of key points
            - "context_around": Background analysis
            - "questioning_the_subject": Cool questions to ask
            - "methods_for_inquiry": Additional resources
        If the operation fails, returns an error message with details.
    """

    prompt = f"""Given the context of "{title}", perform an in-depth analysis of the following news article:

```text
{main_text}
```

Produce a JSON response with the following static keys and corresponding structured data:

- "addressed_topics": A list of exactly 3 key points summarizing the core aspects of the article. Each key point should be concise and insightful.
- "context_around": A list of exactly 3 bullet points that provide background analysis. This should include historical, cultural, or socio-economic factors relevant to the topic, offering external viewpoints for richer context.
- "questioning_the_subject": A list of at least 3 critical questions readers should ask to deepen their understanding of the topic.
- "methods_for_inquiry": A list of at least 3 recommended sources, NOT including websites, but including books, or other reference materials and suggested methodologies for critical engagement with the topic, such as specific tools, techniques, or frameworks.

Ensure the response is strictly in JSON format and adheres to the following template (may change depending on the news article language, you should adapt based on it):

```json
{{
"addressed_topics": [
    "Bullet point 1",
    "Bullet point 2",
    "Bullet point 3"
],
"context_around": [
    "Bullet point 1",
    "Bullet point 2",
    "Bullet point 3"
],
"questioning_the_subject": [
    "Question 1",
    "Question 2",
    "Question 3"
],
"methods_for_inquiry": [
    "Method 1",
    "Method 2",
    "Method 3"
]
}}
```

The output must strictly conform to this structure and contain valid JSON. All generated text should be in the same language as the news article."""

    # Send the request to GPT
    client = OpenAI(api_key=OPENAI_API_KEY)
    response = client.chat.completions.create(
        model="gpt-5-nano",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a helpful and comprehensive assistant designed to output in JSON format. "
                    "Each section should contain well-elaborated, insightful paragraphs, offering a deep dive "
                    "into the respective topics. Ensure that the output, including json keys, is in the same language as the news article and adheres "
                    "to a valid JSON structure, with clear separation between keys and their corresponding textual content."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        n=1,
        response_format={"type": "json_object"},
    )

    output = response.choices[0].message.content
    try:
        summary_data = json.loads(output)  # json input should be validated
    except json.JSONDecodeError:
        summary_data = {}

    return summary_data


def is_inappropriate(
    text: str = "", image_url: str = "", image_stream=None, simple_return: bool = True
):
    if not text and not image_url and not image_stream:
        raise InfomundiCustomException(
            'You should supply "text" or "image_url"/"image_stream" or both.'
        )

    model_input = []

    if text:
        model_input.append({"type": "text", "text": text})

    if image_url:
        model_input.append({"type": "image_url", "image_url": {"url": image_url}})

    if image_stream:
        image_stream.seek(0)  # Ensure we are at the start of the file
        image_bytes = image_stream.read()  # Read file contents

        image_b64 = base64.b64encode(image_bytes).decode("utf-8")
        model_input.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"},
            }
        )

    client = OpenAI(api_key=OPENAI_API_KEY)
    response = client.moderations.create(
        model="omni-moderation-latest", input=model_input
    )

    return response.results[0].flagged if simple_return else response.results[0]


def gpt_chat_about_story(
    title: str,
    main_text: str,
    summary_dict: dict,
    history: list,
    user_message: str,
) -> dict:
    """
    Have Maximus chat about a specific story.
    - Respond concisely, grounded in (title, main_text) and the structured summary.
    - Follow the language of the user's message (fallback: language of the article if clear).
    - Avoid inventing facts; if unknown/not in article context, say so and suggest what to check.

    `history` is a list of {"role":"user"|"assistant", "content":"..."} items.
    Returns: {"text": "<assistant reply>"}
    """
    # Keep history safe and small
    safe_history = []
    for m in history[-10:]:
        if not isinstance(m, dict):
            continue
        role = m.get("role")
        content = m.get("content", "")
        if role in ("user", "assistant") and isinstance(content, str):
            safe_history.append({"role": role, "content": content[:2000]})

    # Compose system prompt with context
    story_context = {
        "title": title,
        "summary": summary_dict or {},
        "article_excerpt": (main_text or "")[:3000],  # budget
    }
    system_text = (
        "You are Maximus, Infomundi's AI assistant. You help users reason about a *specific news story*.\n"
        "GROUNDING:\n"
        "- Use ONLY the provided story context (title, summary, excerpt) and the conversation.\n"
        "- If a claim is not supported by the context, say you don't have enough info.\n"
        "- Offer next steps (what to read/check) instead of guessing.\n\n"
        "STYLE:\n"
        "- Match the user's language.\n"
        "- Keep answers compact and structured (short paragraphs or bullet points).\n"
        "- Include caveats for uncertain info.\n"
        "- When user asks 'what does the article say about X?', answer strictly from context.\n\n"
        f"STORY_CONTEXT (JSON): {json.dumps(story_context, ensure_ascii=False)}"
    )

    client = OpenAI(api_key=OPENAI_API_KEY)
    messages = [{"role": "system", "content": system_text}]
    messages.extend(safe_history)
    messages.append({"role": "user", "content": user_message})

    resp = client.chat.completions.create(
        model="gpt-5-nano",
        messages=messages,
        top_p=1,
        n=1,
        # We want plain text back for the chat bubble
        response_format={"type": "text"},
    )
    text = resp.choices[0].message.content.strip()
    return {"text": text}
