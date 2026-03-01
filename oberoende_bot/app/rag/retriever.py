import os
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings
#from langchain.text_splitter import CharacterTextSplitter
from langchain_text_splitters import CharacterTextSplitter


DB_FAISS_PATH = "faiss_index"

def build_vector_store():
    if os.path.exists(DB_FAISS_PATH):
        return FAISS.load_local(DB_FAISS_PATH, OpenAIEmbeddings(), allow_dangerous_deserialization=True)

    with open("oberoende_bot/app/rag/knowledge.txt", "r", encoding="utf-8") as f:
        text = f.read()

    splitter = CharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    docs = splitter.create_documents([text])

    embeddings = OpenAIEmbeddings()
    vectorstore = FAISS.from_documents(docs, embeddings)
    vectorstore.save_local(DB_FAISS_PATH)

    return vectorstore


vectorstore = build_vector_store()

def retrieve_context(query: str, k: int = 3):
    docs = vectorstore.similarity_search(query, k=k)
    return "\n\n".join([doc.page_content for doc in docs])