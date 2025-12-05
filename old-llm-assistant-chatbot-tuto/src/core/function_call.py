from infra.web_search_rag import *
#from chatbot import grounded_gen
from core.prompt_templates import grounded_generation_prompt
from infra.llm_provider import llm

def grounded_gen(nodes, a, b):
    prompt1 = grounded_generation_prompt(nodes, a, b)
    print(prompt1)
    ai_ans = llm(prompt = prompt1, max_tokens=800, stream=True)
    response = ""
    for t in ai_ans:
        u = t["choices"][0]["text"]
        response = response + u
        print(u, end='', flush=True)
    return {"nodes": nodes, "answer": response, "further_instruct": """Below is a grounded generation by AI that cites source from the web. \
You may now write the final answer to the user incorporating the suggested answer, while also adding your own thoughts as you deem fit. \
Be sure to respect any facts cited and do not override those. *Important*: Please copy the inline citation tags verbatim if you reuse those texts."""}

# Functions for LLM to use

# TODO: need to return dict with further instructions

def web_search_synthesis(search_query: str, topic_question: str) -> str:
    """Synthesize an answer, with inline citations, through searching the web 
    and then passing it through a RAG (Retrieval Augmented Generation) pipeline 
    with a LLM AI.

    The topic_question will be used to select the most relevant text snippets
    in the web search results to feed to the LLM. That LLM will generate an answer
    to the topic_question using the info from the text snippets.

    search_query: Query for the web search engine.
    topic_question: Question to generate answer on.

    Return: Text answer with inline citations.
    """
    do_web_search_synthesis(search_query, topic_question)

def code_interpreter(request: str) -> str:
    """Initiate a code interpreter session to solve problem, or do things on the 
    user's behave, via running python program designed by an AI.

    request: A fully self contained text instruction on what the AI should
      accomplish within the code interpreter session. Example: "Generate a plot of
      the price of SP500 in the last week, and save it to the file sp_500_price.png."
    
    Return: Text remarks from the code interpreter AI.
    """
    run_code_interpreter(request)

def do_web_search_synthesis(a, b):
    print("do_web_search_synthesis")
    print(a, b)
    web_search_results = web_search(a)
    print(web_search_results)
    mydocs = gen_docs(web_search_results)
    print(len(mydocs))
    chroma_client = chromadb.EphemeralClient()
    try:
        chroma_client.delete_collection("temp")
    except BaseException as e:
        print(e)
    embed_model = HuggingFaceEmbedding(model_name="intfloat/e5-small-v2", embed_batch_size=200)
    topic_q = b
    if b is None or b == "":
        topic_q = "Give a relevant summary of the search query: " + a
    mynodes = query_crawl(mydocs, topic_q, 5, embed_model, chroma_client)
    print(mynodes)
    #nodes[0].metadata, nodes[0].text
    return grounded_gen(mynodes, a, b)


def run_code_interpreter(r):
    print("run_code_interpreter") # TODO: implement code interpreter
    print(r)

function_registry = {
    "web_search_synthesis": web_search_synthesis,
    "code_interpreter": code_interpreter
}
