from openai import OpenAI
import os

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))



def strip_json_fences(content: str) -> str:
    if content.startswith("```"):
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]
    return content.strip()



#----------------azure api key connecting code ---------------------


# # Changed to (Azure):
# from openai import AzureOpenAI
# client = AzureOpenAI(
#     api_key=os.getenv("AZURE_OPENAI_API_KEY"),
#     azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
#     api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
# )

