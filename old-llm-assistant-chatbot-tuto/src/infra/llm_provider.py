from llama_cpp import Llama, LlamaDiskCache

LOCAL_PATH = "/home/zeus/.cache/huggingface/hub/models--mradermacher--bagel-8b-v1.0-GGUF/snapshots/2b34e5c62aa0af4fb2dbc9a120e78ee357d0b026/bagel-8b-v1.0.Q6_K.gguf"


llm = Llama(model_path=LOCAL_PATH, n_ctx=8192)
llm.set_cache(LlamaDiskCache(capacity_bytes=(2 << 30)))

def stream_completion_outputs(llm_stream):
    response = ""
    for t in llm_stream:
        u = t["choices"][0]["text"]
        response = response + u
        print(u, end='', flush=True)
        #break
    return response
