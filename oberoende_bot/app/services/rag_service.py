import os
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import TextLoader, PyPDFLoader, Docx2txtLoader

VECTORSTORE_PATH = "oberoende_bot/app/data/vectorstore"
DOCUMENTS_PATH = "oberoende_bot/app/data/documentos"


vectorstore_instance = None  # <- variable global


def load_documents():
    documents = []

    for file in os.listdir(DOCUMENTS_PATH):
        filepath = os.path.join(DOCUMENTS_PATH, file)

        if file.endswith(".docx"):
            loader = Docx2txtLoader(filepath)
        elif file.endswith(".pdf"):
            loader = PyPDFLoader(filepath)
        elif file.endswith(".txt"):
            loader = TextLoader(filepath, encoding="utf-8")
        else:
            continue
        print(f"📄 Loader: {loader}")
        documents.extend(loader.load())
    
    return documents


def create_vectorstore():
    documents = load_documents()

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=100
    )

    docs = splitter.split_documents(documents)

    embeddings = OpenAIEmbeddings()

    vectorstore = FAISS.from_documents(docs, embeddings)

    vectorstore.save_local(VECTORSTORE_PATH)

    return vectorstore


def initialize_vectorstore(force_rebuild: bool = False):
    global vectorstore_instance

    embeddings = OpenAIEmbeddings()

    if force_rebuild:
        print("♻️ Forzando recreación del vectorstore...")
        vectorstore_instance = create_vectorstore()
        return

    if os.path.exists(VECTORSTORE_PATH):
        print("🔄 Cargando vectorstore desde disco...")
        vectorstore_instance = FAISS.load_local(
            VECTORSTORE_PATH,
            embeddings,
            allow_dangerous_deserialization=True
        )
    else:
        print("🆕 Creando vectorstore nuevo...")
        vectorstore_instance = create_vectorstore()


def get_vectorstore():
    return vectorstore_instance