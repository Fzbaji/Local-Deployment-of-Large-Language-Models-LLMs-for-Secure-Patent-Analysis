import streamlit as st
import requests
import json
from time import sleep
from fpdf import FPDF
import os
import fitz  # PyMuPDF
from langchain_community.vectorstores import Chroma
from langchain.prompts import ChatPromptTemplate
from langchain_community.llms.ollama import Ollama
from get_embedding_function import get_embedding_function
from populate_database import run as populate_database_main
from langchain.text_splitter import CharacterTextSplitter
from langchain_core.documents import Document
from langchain.schema import Document
from ingest import initialize_vector_store  # Adapté de l’autre projet
import pdfplumber

# ------------ Utilitaires ---------------

def clean_text(text):
    return text.encode("latin-1", errors="ignore").decode("latin-1")


def extract_and_ingest_pdf(file):
    with pdfplumber.open(file) as pdf:
        text = ""
        for page in pdf.pages:
            text += page.extract_text() or ""

    doc = Document(page_content=text)
    splitter = CharacterTextSplitter.from_tiktoken_encoder(chunk_size=1000, chunk_overlap=200)
    splits = splitter.split_documents([doc])

    db = initialize_vector_store()  # from ingest.py
    db.add_documents(splits)
    db.persist()
    return db


from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from langchain_community.chat_models import ChatOllama
from langchain_core.prompts import ChatPromptTemplate

def ask_question_with_rag(db, question):
    retriever = db.as_retriever(k=3)
    model = ChatOllama(model="llama3.2")

    prompt_template = ChatPromptTemplate.from_template("""
    Answer the question based only on the following context:
    
    {context}
    
    Question: {question}
    
    If the answer is not in the context, reply with: "Sorry, I couldn't find relevant information in the document."
    """)

    chain = (
        {"context": retriever, "question": RunnablePassthrough()}
        | prompt_template
        | model
        | StrOutputParser()
    )

    return chain.invoke(question)


# ------------ PatentFetcher ---------------

class PatentFetcher:
    def __init__(self):
        self.api_key = "CQSd3FBT.8vmxye4Np3EBjNgPMwadolmTjQhg5TJr"
        self.base_url = "https://search.patentsview.org/api/v1/patent/"
        self.headers = {
            "Content-Type": "application/json",
            "X-Api-Key": self.api_key
        }
        self.delay = 0.6

    def fetch_patents(self, keyword=None, max_pages=1):
        all_patents = []
        page = 1
        progress_bar = st.progress(0)
        status_text = st.empty()

        while page <= max_pages:
            query = {
                "q": {
                    "_or": [
                        {"_text_any": {"patent_title": keyword}},
                        {"_text_any": {"patent_abstract": keyword}}
                    ]
                },
                "f": ["patent_id", "patent_title", "patent_abstract", "patent_date"],
                "o": {"page": page, "per_page": 100}
            }

            try:
                status_text.text(f"Fetching page {page}/{max_pages}...")
                progress_bar.progress(page / max_pages)

                response = requests.post(self.base_url, headers=self.headers, data=json.dumps(query), timeout=20)
                if response.status_code != 200:
                    st.error(f"Error {response.status_code}: {response.text}")
                    break

                data = response.json()
                patents = data.get("patents", [])
                if not patents:
                    break

                all_patents.extend(patents)
                page += 1
                sleep(self.delay)

            except Exception as e:
                st.error(f"Error: {str(e)}")
                break

        progress_bar.empty()
        status_text.empty()
        return all_patents


def save_patents_to_pdf(patents, keyword):
    os.makedirs("data", exist_ok=True)
    safe_keyword = clean_text("".join(c for c in keyword if c.isalnum() or c in (' ', '_')).rstrip())
    filename = os.path.join("data", f"{safe_keyword}.pdf")

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Arial", size=12)

    for i, patent in enumerate(patents, 1):
        title = clean_text(patent.get('patent_title', 'No title'))
        date = patent.get('patent_date', 'Unknown')
        pid = patent.get('patent_id', 'Unknown')
        abstract = clean_text(patent.get('patent_abstract', 'No abstract'))

        pdf.set_font("Arial", 'B', 12)
        pdf.multi_cell(0, 10, f"{i}. {title}")

        pdf.set_font("Arial", '', 11)
        pdf.cell(0, 8, f"Date: {date} | ID: {pid}", ln=True)
        pdf.multi_cell(0, 8, f"Abstract: {abstract}")
        pdf.ln(5)

    pdf.output(filename)
    return filename


def run_populate_database():
    try:
        populate_database_main()
        st.success("Chroma DB mise à jour avec succès.")
    except Exception as e:
        st.error(f"Erreur lors de la mise à jour de la base : {e}")

# ------------ UI ---------------

def search_page():
    st.title("🔍 Recherche de brevets")
    keyword = st.text_input("Entrez un mot-clé (titre ou résumé) :")
    max_pages = st.slider("Nombre de pages à rechercher :", 1, 5, 1)

    if st.button("Rechercher"):
        if keyword:
            fetcher = PatentFetcher()
            patents = fetcher.fetch_patents(keyword=keyword, max_pages=max_pages)

            if patents:
                st.success(f"{len(patents)} brevets trouvés.")
                st.session_state["patents"] = patents
                st.session_state["keyword"] = keyword
            else:
                st.warning("Aucun brevet trouvé.")
        else:
            st.warning("Veuillez saisir un mot-clé.")

    if "patents" in st.session_state:
        st.subheader("📋 Résumés des brevets trouvés :")

        for i, patent in enumerate(st.session_state["patents"], 1):
            with st.expander(f"{i}. {patent.get('patent_title', 'Titre non disponible')}"):
                st.write(f"📅 Date : {patent.get('patent_date', 'Inconnue')}")
                st.write(f"🆔 ID : {patent.get('patent_id', 'Inconnu')}")
                st.write(f"📝 Résumé : {patent.get('patent_abstract', 'Résumé non disponible')}")
                pid = patent.get("patent_id", "")
                if pid:
                    google_link = f"https://patents.google.com/patent/US{pid}"
                    st.markdown(f"[📥 Télécharger PDF sur Google Patents]({google_link})")

        if st.button("📄 Générer PDF et passer au chatbot"):
            pdf_file = save_patents_to_pdf(st.session_state["patents"], st.session_state["keyword"])
            st.success(f"PDF généré : {pdf_file}")
            st.write("🔄 Mise à jour de la base de données RAG...")
            run_populate_database()
            st.success("✅ Base de données Chroma mise à jour.")
            st.session_state.page = "chatbot"
            st.rerun()


def chatbot_page():
    st.title("💬 Chatbot - Brevets")
    
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    st.subheader("📤 Importer un PDF personnel")
    uploaded_file = st.file_uploader("Choisir un fichier PDF", type=["pdf"])

    if uploaded_file:
        st.info("📄 Lecture et indexation du fichier PDF...")
        db = extract_and_ingest_pdf(uploaded_file)
        st.success("✅ Document importé et indexé dans la base de données.")

        st.session_state.vector_db = db

    user_input = st.chat_input("Posez votre question sur ce document")

    if user_input and "vector_db" in st.session_state:
        response = ask_question_with_rag(st.session_state.vector_db, user_input)
        st.session_state.chat_history.append(("Vous", user_input))
        st.session_state.chat_history.append(("Assistant", response))
    elif user_input:
        st.warning("Veuillez importer un document PDF d'abord.")

    for sender, message in st.session_state.chat_history:
        with st.chat_message(sender):
            st.markdown(message)


def main():
    st.set_page_config(page_title="Patent Assistant", layout="wide")
    page = st.sidebar.selectbox("Navigation", ["🔍 Rechercher des brevets", "💬 Chatbot"])
    if page == "🔍 Rechercher des brevets":
        search_page()
    elif page == "💬 Chatbot":
        chatbot_page()


if __name__ == "__main__":
    main()
