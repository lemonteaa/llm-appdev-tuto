# Sample RAG chatbot

security_warning = """
Update (2025 Nov):
Due to what seem like to be increased enforcement from duckduckgo, the `duckduckgo-search` library, which is pretty
much the only python lib providing api-like access, doesn't really work in more recent time. By itself, this would be
sad but understandable. However, the library was updated with a drastic change in what it actually does:
- it is now a metasearch engine - **and it includes backend that privacy sensitive user may find completely unacceptable**
- this change is **implicit and automatic with no warning given to user** - unsuspecting user may end up accidentally sabotaging their privacy
- And the name is reinterpreted - **DDGS now means Dux Distributed Global Search**, which has the same initial as duck duck go search,
  so that user who didn't dig deep may not realize the full ramification of continuing to use the library (by contrast, if the library is
  renamed to say "metasearch aggregator", then at least privacy sensitive user may more easily notice what's going on and make an informed
  choice themselves.)

Now, I have nothing against that library itself - they have full right to decides what to do with the library. However,
given the situation listed above, in an abundance of caution, I have disabled the relevant code below. As an end user,
it is up to you to decide whether you want to proceed or not.
"""

from transformers import AutoTokenizer

import json
import re

#from duckduckgo_search import DDGS

from llama_index.readers.web import SimpleWebPageReader

import chromadb
from llama_index.core import VectorStoreIndex
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.core import StorageContext
from llama_index.embeddings.huggingface import HuggingFaceEmbedding

from llama_index.core.node_parser import TokenTextSplitter

def extract_action(text):
    cap_grp = re.search("```(json|js|javascript)?([\s\S]*)```", text).group(2)
    return json.loads(cap_grp)

# Uncomment only if you really know what you are doing
#def web_search(q):
#    results = DDGS().text(q + " filetype:html", max_results=10)
#    return results
def web_search(q):
    raise RuntimeError(security_warning)


#def gen_docs(search_results):
#    docs = SimpleWebPageReader(html_to_text=True).load_data([result['href'] for result in search_results])
#    for result, doc in zip(search_results, docs):
#        doc.metadata = { 'title': result['title'], 'href': result['href'] }
#    return docs

def gen_docs(search_results):
    #docs = SimpleWebPageReader(html_to_text=True).load_data([result['href'] for result in search_results])
    docs = []
    for result in search_results:
        try:
            doc = SimpleWebPageReader(html_to_text=True).load_data([ result['href'] ])[0]
            doc.metadata = { 'title': result['title'], 'href': result['href'] }
            docs.append(doc)
        except BaseException as e:
            print(e)
    return docs

def query_crawl(docs, query, top_k, embed_model, chroma_client):
    chroma_collection = chroma_client.create_collection("temp")
    vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    index = VectorStoreIndex.from_documents(docs, storage_context=storage_context, embed_model=embed_model)
    retriever = index.as_retriever(similarity_top_k=top_k)
    nodes = retriever.retrieve(query)
    return nodes

