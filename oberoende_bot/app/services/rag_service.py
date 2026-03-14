import os
from typing import Dict, Optional

from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import TextLoader, PyPDFLoader, Docx2txtLoader

from oberoende_bot.app.config.businesses import BUSINESSES

vectorstore_instances: Dict[str, FAISS] = {}


def load_documents(documents_path: str):
    documents = []

    if not os.path.exists(documents_path):
        print(f"⚠️ No existe carpeta de documentos: {documents_path}")
        return documents

    for file in os.listdir(documents_path):
        filepath = os.path.join(documents_path, file)

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


def create_vectorstore(documents_path: str, vectorstore_path: str):
    documents = load_documents(documents_path)
    if not documents:
        return None

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=100
    )

    docs = splitter.split_documents(documents)
    embeddings = OpenAIEmbeddings()
    vectorstore = FAISS.from_documents(docs, embeddings)

    os.makedirs(os.path.dirname(vectorstore_path), exist_ok=True)
    vectorstore.save_local(vectorstore_path)
    return vectorstore


def initialize_vectorstore_for_business(
    business_id: str,
    force_rebuild: bool = False
) -> Optional[FAISS]:
    config = BUSINESSES[business_id]
    documents_path = config["documents_path"]
    vectorstore_path = config["vectorstore_path"]

    embeddings = OpenAIEmbeddings()

    if force_rebuild:
        print(f"♻️ Forzando recreación del vectorstore para {business_id}...")
        vs = create_vectorstore(documents_path, vectorstore_path)
        if vs is not None:
            vectorstore_instances[business_id] = vs
        return vs

    if os.path.exists(vectorstore_path):
        print(f"🔄 Cargando vectorstore de {business_id} desde disco...")
        vs = FAISS.load_local(
            vectorstore_path,
            embeddings,
            allow_dangerous_deserialization=True
        )
        vectorstore_instances[business_id] = vs
        return vs

    print(f"🆕 Creando vectorstore nuevo para {business_id}...")
    vs = create_vectorstore(documents_path, vectorstore_path)
    if vs is not None:
        vectorstore_instances[business_id] = vs
    return vs


def initialize_all_vectorstores(force_rebuild: bool = False):
    for business_id in BUSINESSES.keys():
        try:
            initialize_vectorstore_for_business(business_id, force_rebuild=force_rebuild)
        except Exception as e:
            print(f"⚠️ Error inicializando vectorstore para {business_id}: {e}")


def get_vectorstore(business_id: str):
    return vectorstore_instances.get(business_id)