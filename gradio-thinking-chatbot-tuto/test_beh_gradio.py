import gradio as gr
from gradio import ChatMessage

import time

# Only content from yield counts but not the return value

def simulate_thinking_chat(message, history, conversation):
    print(conversation)
    responses = []
    responses.append({ "role": "assistant", "content": "I am thinking step 1...", "metadata": { "title": "Thinking...", "status": "pending", "id": 1 } })
    responses.append({ "role": "assistant", "content": "", "metadata": { "title": "Use tool `web_search` with query **Hello world**", "status": "pending", "id": 2, "parent_id": 1 } })
    responses.append({ "role": "assistant", "content": "", "metadata": { "title": "Use tool `web_search` with query **tech singularity**", "status": "pending", "id": 3, "parent_id": 1 } })
    yield responses
    time.sleep(1.5)
    responses[-2]["content"] = "Returned 3 relevant results."
    responses[-1]["content"] = "Returned 5 relevant results."
    responses[-2]["metadata"]["status"] = "done"
    responses[-1]["metadata"]["status"] = "done"
    yield responses
    time.sleep(3.5)
    responses.append({ "role": "assistant", "content": "Let me continue to think step 2 based on the results above...", "metadata": { "title": "Thinking...", "id": 4 } })
    responses.append({ "role": "assistant", "content": "Testing concept...", "metadata": { "parent_id": 4 } })
    yield responses
    time.sleep(3)
    responses[0]["metadata"]["status"] = "done"
    responses.append({ "role": "assistant", "content": "## Analysis\nThere are some point:\n- Consider this\n- And then that\n\n**Here** is the final answer: $$\\boxed{ 42 }$$." })
    yield responses
    time.sleep(0.5)
    responses[-1]["options"] = [{ "value": "Can I try too?" }, { "value": "But What about this" }]
    yield responses
    conversation.append("testing111")
    #return responses, conversation




demo = gr.ChatInterface(
    simulate_thinking_chat,
    title="Thinking LLM Chat Interface 🤔",
    type="messages",
    chatbot=gr.Chatbot(layout="panel", type="messages"),
    examples=[["Hello"], ["More"]],
    additional_inputs=[gr.State(value=[])],
    #additional_outputs=[gr.State()]
)

demo.launch(server_port=7861)
