import requests
import time

"""
Tool registry
"""

from collections import OrderedDict
import traceback

class ToolRegistry:
    def __init__(self):
        self.tools = OrderedDict()
    
    def register_tool(self, name, desc, schema, fn, is_async=False, ui_display_fn=lambda tool_args: "Calling tool..."):
        self.tools[name] = { "name": name, "desc": desc, "schema": schema.model_json_schema(), "fn": fn, "is_async": is_async, "ui_display_fn": ui_display_fn }
    
    def get_tool_list(self):
        tool_list = []
        for k_name, v_detail in self.tools.items():
            openai_tool_spec = {
                'type': 'function',
                'function': {
                    'name': k_name,
                    'description': v_detail["desc"],
                    'parameters':  v_detail["schema"],
                    'strict': True
                }
            }
            tool_list.append(openai_tool_spec)
        return tool_list
    
    def call_tool_dynamic_single_sync_raw(self, name, tool_args):
        try:
            fn = self.tools[name]["fn"]
            result = fn(**tool_args)
            return result
        except Exception as e:
            traceback.print_exc()
            diagnostic = f'{e.__class__.__module__}.{e.__class__.__name__}: {e} {repr(e)}'
            print(diagnostic)
            return f"Encountered Error for this instance of tool use: {diagnostic}"
    
    def get_tool_call_ui_display(self, name, tool_args):
        return self.tools[name]["ui_display_fn"](tool_args)

central_tool_registry = ToolRegistry()

"""
Tool spec
"""

from pydantic import BaseModel, Field
import json


class WebSearchParam(BaseModel):
     model_config = dict(extra='forbid')
     query : str = Field(description="The search query. Can use advanced search syntax in search engine. Will be prepended with !br to scope the search to using brave since we're using a metasearch engine.")
     language : str = Field(default="en", description="Prioritize results to pages in the specified language first.")
     time_range: str = Field(default="year", description="Return results in a time range. Possible values are day, week, month, year.")

web_search_tool_desc = 'Perform *one* web search using a metasearch engine.'


class ExtractWebpageParam(BaseModel):
    model_config = dict(extra='forbid')
    url: str = Field(description="The URL of the webpage to visit.")
    topic_question: str = Field(default="Please provide a concise summary of the key information and/or viewpoint presented in the document.", description="A question used to direct the AI coworker as it read the content of the webpage at `url`.")

extract_webpage_tool_desc = 'Assign an AI coworker to read the webpage and extract information in the webpage that are relevant to answering user query.'


"""
Prompts
"""

system_prompt = """You are an AI assistant deployed as a chatbot.

### Behavior guideline

- You should leverage the tool when appropriate, based on your situational judgement, to fulfill user requests.
- When using tool, you should exploit the fact that you can call multiple tool at once for efficiency. However, balance this with resource usage. For web search, at most 3 queries each time. For extracting webpage, at most 10 page each time.
- Do not hallucinate. Only use the extract webpage tool on URL found in web search result (we are in dev mode and any 404 error due to you trying to remember URL from memory will trip up the app).
- You use Tool integrated reasoning (TIR) in interleaved thinking mode. So you can continue to think (and further use tool in second or more rounds) after receiving tool response. Repeat until you're satisfied that you can answer.
- When giving final answer to user, if you are using information found in a webpage, you should cites it using suitable markdown syntax. With multiple source, make sure citation are assigned to the correct source (i.e. do not mix it up such as citing #3 to a fact found in #2, and vice versa). Citation should include source URL.
- Typical workflow: 1) General web search, then select webpages based on snippet in search result, and send them to `extract_webpage` to get a more detailed read by your AI coworker. 2) Can also directly extract specific webpage if the URL is provided by user. (This does not contradict the URL carefulness requirement above, because the chatbot prioritize user experience.)
"""

user_query_example_01 = "There is a saying that Fusion power is always just ten years away - it is a half joke about how the impression the general public get is that science is always having a major breakthrough and is about to solve fusion, when the actual state of progress is a more complicated story. May also have to do with media hyping and setting up over-expectation. But don't you think there is still legit progress? Hence, can you gather some recent news on this, and find what are the (professional) physics communities' mainstream opinion based on the latest advances/understanding."


def read_webpage_prompt_template(doc, topic_question):
    return [
        { "role": "system", "content": "You are a document summarizer/webpage info extractor. Follow the user instruction below. Note that your answer will be sent back to the main AI for further processing (but the main AI cannot otherwise see the webpage you see. This is an automated pipeline with single turn, massively parallel (of which you are one of the many instance), used in a semi-realtime way where speed is slightly more important than quality, so keep things straight forward and do not overthink." },
        { "role": "user", "content": "Following is a webpage (parsed into markdown but no special processing so expect some messiness such as menubar etc):\n\n" + doc + f"\n\n----\n\nTask: Read the document above and based only on it, write a response to the following topic question: {topic_question}. If the document did not provide relevant information to the topic question, simply state so without adding your own existing knowledge."}
    ]


"""
Define the tools fn and register
"""

from selenium import webdriver
from bs4 import BeautifulSoup
from markdownify import markdownify as md

import urllib.parse

driver = webdriver.Firefox()

def web_search(query, language="en", time_range="year"):
    q_escaped = urllib.parse.quote(query, safe='')
    driver.get(f"https://search.hbubli.cc/search?q=%21br%20{q_escaped}&language={language}&time_range={time_range}&safesearch=0&pageno=1&categories=none")
    html = driver.page_source
    dom = BeautifulSoup(html, 'html.parser')
    mydivs = dom.find_all("article", {"class": "result"})
    search_result = []
    for entry in mydivs:
        search_result.append( md(str(entry), strip=['img', 'svg']) )
    return "\n\n\n".join(search_result)

def extract_webpage(url : str, topic_question="Please provide a concise summary of the key information and/or viewpoint presented in the document."):
    get_res = requests.get(url)
    doc = md(get_res.content)
    res_side = cli.chat.completions.create(
        model="qwen3",
        messages=read_webpage_prompt_template(doc, topic_question)
    )
    return f"### Document summary info for {url}\n\n" + res_side.choices[0].message.content


central_tool_registry.register_tool(name='web_search', desc=web_search_tool_desc, schema=WebSearchParam, fn=web_search, ui_display_fn=lambda tool_args: f"Calling `web_search` with query **{tool_args["query"]}**")
central_tool_registry.register_tool(name='extract_webpage', desc=extract_webpage_tool_desc, schema=ExtractWebpageParam, fn=extract_webpage, ui_display_fn=lambda tool_args: f"Reading webpage {tool_args["url"]}")


"""
Init OpenAI Client
"""
from openai import OpenAI

cli = OpenAI(
    base_url="<your base url>",
    api_key="<your api key, should use env var etc>"
)

"""
Gradio Demo (Frontend)
"""

import gradio as gr
from gradio import ChatMessage

import uuid

"""
@dataclass
class ChatMessage:
   content: str | Component
   metadata: MetadataDict = None
   options: list[OptionDict] = None

class MetadataDict(TypedDict):
   title: NotRequired[str]
   id: NotRequired[int | str]
   parent_id: NotRequired[int | str]
   log: NotRequired[str]
   duration: NotRequired[float]
   status: NotRequired[Literal["pending", "done"]]

class OptionDict(TypedDict):
   label: NotRequired[str]
   value: str
"""

def main_call_llm(message_list):
    res = cli.chat.completions.create(
        model="qwen3",
        messages=message_list,
        tools=central_tool_registry.get_tool_list(),
        parallel_tool_calls=True,
        extra_body={ "parse_tool_calls": True }
    )
    return res


def gradio_chat_fn(message, history, conversation):
    conversation.append({ "role": "user", "content": message })
    done = False
    ui_msg = []
    # Frontend: add dummy node
    full_msg_id = str(uuid.uuid4())
    ui_msg.append({ "role": "assistant", "content": "", "metadata": { "title": "Thinking...", "status": "pending", "id": full_msg_id } })
    yield ui_msg
    
    while not done:
        # Call LLM
        res = main_call_llm(conversation)
        conversation.append(res.choices[0].message)
        if res.choices[0].finish_reason == 'tool_calls':
            # Frontend: add reasoning step
            ui_msg.append({ "role": "assistant", "content": res.choices[0].message.reasoning_content, "metadata": { "title": "", "id": res.id, "parent_id": full_msg_id } })
            n_parallel_call = len(res.choices[0].message.tool_calls)
            for tool_call in res.choices[0].message.tool_calls:
                fn = tool_call.function
                f_args = json.loads(fn.arguments)
                f_id = tool_call.id
                # Frontend: Add the init'ed tool call
                display_title = central_tool_registry.get_tool_call_ui_display(fn.name, f_args)
                ui_msg.append({ "role": "assistant", "content": "", "metadata": { "title": display_title, "status": "pending", "id": f_id, "parent_id": full_msg_id } })
            yield ui_msg
            for idx, tool_call in enumerate(res.choices[0].message.tool_calls):
                fn = tool_call.function
                f_args = json.loads(fn.arguments)
                f_id = tool_call.id
                # Backend: run the tool
                f_ret = central_tool_registry.call_tool_dynamic_single_sync_raw(fn.name, f_args)
                # Update the frontend display
                ui_msg[-(n_parallel_call - idx)]["metadata"]["status"] = "done"
                yield ui_msg
                # Backend: append reply to prepare next round
                conversation.append({ "role": "tool", "tool_call_id": f_id, "content": f_ret })
        else:
            # Frontend only: final update
            ui_msg.append({ "role": "assistant", "content": res.choices[0].message.reasoning_content, "metadata": { "title": "", "id": res.id, "parent_id": full_msg_id } })
            ui_msg.append({ "role": "assistant", "content": res.choices[0].message.content })
            yield ui_msg
            time.sleep(2)
            i = -2
            found_dummy_root = False
            while not found_dummy_root:
                if ui_msg[i]["metadata"]["id"] == full_msg_id:
                    ui_msg[i]["metadata"]["status"] = "done"
                    yield ui_msg
                    found_dummy_root = True
                else:
                    i = i - 1
            done = True



demo = gr.ChatInterface(
    gradio_chat_fn,
    title="Thinking LLM Chat Interface 🤔",
    type="messages",
    chatbot=gr.Chatbot(layout="panel", type="messages", min_height=1000),
    examples=[["Hello there"], [user_query_example_01]],
    additional_inputs=[gr.State(value=[ { "role": "system", "content": system_prompt } ])],
    #additional_outputs=[gr.State()]
)

demo.launch(server_port=7861)


