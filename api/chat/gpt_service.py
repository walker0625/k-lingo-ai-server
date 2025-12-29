import os
from openai import OpenAI

def ask_gpt4o(system, question):
    
    client = os.getenv("OPENAI_API_KEY")
    
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": question}
        ]
    )
    
    return response.choices[0].message.content