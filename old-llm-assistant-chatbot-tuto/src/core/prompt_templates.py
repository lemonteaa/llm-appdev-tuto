import outlines

@outlines.prompt
def system_inst(sys, funcs, eg):
    """{{ sys }}
    Available functions:
    {% for f in funcs %}
    {{ f | source }}
    {% endfor %}
    {{ eg }}
    """

@outlines.prompt
def chatml_template(messages, nudge_role = "assistant"):
    """
    {% for m in messages %}
    <|im_start|>{{ m['role'] }}
    {{ m['content'] }}
    <|im_end|>
    {% endfor %}
    <|im_start|>{{ nudge_role }}
    """

system_prompt = \
"""As an AI assistant, you will answer user queries. When necessary, you can call the \
following functions to help you. Answer to user are done by sending a message to the \
user, identifying yourself as the assistant role via `<|im_start|>assistant`, \
while function calls are done by sending a special message to the function role implicitly \
via `<|im_start|>function` (Here the purpose is not to identify yourself, but to indicate \
that the message is for internal use). When sending to the function role, use \
the JSON format: a JSON object with attr "function" (For the function name) and "params" (a \
JSON object whose keys are the argument name, and the respective value are the correspdoning \
value of that argument). Function call return value (if any) will \
be sent to you as a message \
from system role, with further instruction on what you should do next also given there.

You are an open source AI assistant made by an annoymous person. You are cheerful, creative, \
but also thoughtful.
"""

eg = """Examples:
User> hi, how are you?
Correct role choice: assistant

User> What are some latest news in <topic>?
Correct role choice: function

User> Can you generate a graph of the SP500 today?
Correct role choice: function

User> Suggest some interior design for my new home.
Correct role choice: assistant
"""


fn_schema = """
{
    "title": "FunctionCall",
    "type": "object",
    "properties": {
        "function": { "type": "string", "enum": ["web_search_synthesis", "code_interpreter"] },
        "params": { "type": "object" }
    },
    "required": ["function", "params"]
}
"""

#nodes[0].metadata, nodes[0].text

@outlines.prompt
def grounded_generation_prompt(mynodes, search_query, topic_question):
    """
BEGININPUT
{% for node in mynodes %}
BEGINCONTEXT
id: {{ loop.index }}
title: {{ node.metadata["title"] }}
ENDCONTEXT
{{ node.text }}
{% endfor %}
ENDINPUT
BEGININSTRUCTION
<system>Answer user query based on provided information above. In your answer, cite the sources *inline* using a special tag. Example:
```
It is known that current progress in AI is <cite:3>expected to accelerates by some experts</cite>, although other disagree.
```
Where the number inside the tag is the source id. </system>
Topic question: {{ topic_question }}
(If topic question is empty, infer what the user want to ask based on the search query below and answer that instead:
Search query: {{ search_query }})
ENDINSTRUCTION
    """
