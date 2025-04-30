import json
import base64
from random import choice as random_choice
from requests import get as get_request
from bs4 import BeautifulSoup
from openai import OpenAI

from .custom_exceptions import InfomundiCustomException
from .config import OPENAI_API_KEY
from .immutable import USER_AGENTS


def gpt_summarize(url: str) -> dict:
    """Summarize a news article from the provided URL and structure the response for integration with the JavaScript.

    Args:
        url (str): The URL of the news article to summarize.

    Returns:
        dict: A dictionary with the structured summary:
            - "addressed_topics": List of key points
            - "context_around": Background analysis
            - "where_can_i_find_more_information?": Additional resources
        If the operation fails, returns an error message with details.
    """

    try:
        # Fetch the article content
        r = get_request(
            url, timeout=5, headers={"User-Agent": random_choice(USER_AGENTS)}
        )
        if r.status_code not in (200, 301, 302):
            return {"error": "Failed to fetch the article. Invalid status code."}

        # Parse the article content
        soup = BeautifulSoup(r.content, "lxml")
        news_title = soup.title.string.strip() if soup.title else "News Article"
        article_text = " ".join([p.get_text().strip() for p in soup.find_all("p")])[
            :1500
        ]

        prompt = f"""Given the context of "{news_title}", perform an in-depth analysis of the following news article:

```text
{article_text}
```

Produce a JSON response with the following static keys and corresponding structured data:

- "addressed_topics": A list of exactly 3 key points summarizing the core aspects of the article. Each key point should be concise and insightful.
- "context_around": A list of exactly 3 bullet points that provide background analysis. This should include historical, cultural, or socio-economic factors relevant to the topic, offering external viewpoints for richer context.
- "questioning_the_subject": A list of at least 3 critical questions readers should ask to deepen their understanding of the topic.
- "methods_for_inquiry": A list of at least 3 recommended sources, NOT including websites, but including books, or other reference materials and suggested methodologies for critical engagement with the topic, such as specific tools, techniques, or frameworks.

Ensure the response is strictly in JSON format and adheres to the following template:

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
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a helpful and comprehensive assistant designed to output in JSON format. "
                        "Each section should contain well-elaborated, insightful paragraphs, offering a deep dive "
                        "into the respective topics. Ensure that the output, including json keys, is in the same language as the one in the news article and adheres "
                        "to a valid JSON structure, with clear separation between keys and their corresponding textual content."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            n=1,
            response_format={"type": "json_object"},
            temperature=0,
        )

        # Parse and validate JSON output
        output = response.choices[0].message.content
        try:
            summary_data = json.loads(output)
            return summary_data
        except json.JSONDecodeError:
            return {"error": "GPT response is not valid JSON.", "response": output}

    except Exception as e:
        return {"error": "An error occurred during summarization.", "details": str(e)}


def is_inappropriate(
    text: str = "", image_url: str = "", image_stream=None, simple_return: bool = True
) -> bool:
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
