import streamlit as st
import requests
import json
from time import sleep
from fpdf import FPDF
import os
import uuid
import fitz  # PyMuPDF
import shutil
import atexit
from langchain_community.vectorstores import Chroma
from langchain.prompts import ChatPromptTemplate
from langchain_community.llms.ollama import Ollama
from get_embedding_function import get_embedding_function
from langchain.text_splitter import RecursiveCharacterTextSplitter

# ------------ Utilitaires ---------------

def clean_text(text):
    return text.encode("latin-1", errors="ignore").decode("latin-1")

def extract_text_from_pdf(pdf_file):
    text = ""
    with fitz.open(stream=pdf_file.read(), filetype="pdf") as doc:
        for page in doc:
            text += page.get_text()
    return text

def query_rag(query_text: str, db_path: str):
    db = Chroma(
        persist_directory=db_path,
        embedding_function=get_embedding_function()
    )

    results = db.similarity_search_with_score(query_text, k=5)

    if not results:
        return "Je n'ai trouvé aucune information pertinente dans la base."

    context_text = "\n\n---\n\n".join([doc.page_content for doc, _ in results])
    
    prompt_template = ChatPromptTemplate.from_template("""
You are an assistant who is an expert in patents. Answer the question based only on the following context:

{context}

---

Answer the question based on the above context: {question}
""")

    prompt = prompt_template.format(context=context_text, question=query_text)

    model = Ollama(model="mistral")
    return model.invoke(prompt)

# ------------ Classes API ---------------

class PatentFetcher:
    def _init_(self):
        self.api_key = "CQSd3FBT.8vmxye4Np3EBjNgPMwadolmTjQhg5TJr"
        self.base_url = "https://search.patentsview.org/api/v1/patent/"
        self.headers = {
            "Content-Type": "application/json",
            "X-Api-Key": self.api_key
        }
        self.delay = 0.6

    def fetch_patents(self, keyword=None, page_start=1, page_end=3):
        all_patents = []
        page = page_start
        total_pages = page_end - page_start + 1

        progress_bar = st.progress(0)
        status_text = st.empty()

        while page <= page_end:
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
                status_text.text(f"Récupération page {page}/{page_end}... (PatentsView)")
                progress_bar.progress((page - page_start + 1) / total_pages)

                response = requests.post(self.base_url, headers=self.headers, data=json.dumps(query), timeout=20)
                if response.status_code != 200:
                    st.error(f"Erreur {response.status_code}: {response.text}")
                    break

                data = response.json()
                patents = data.get("patents", [])
                if not patents:
                    break

                all_patents.extend(patents)
                page += 1
                sleep(self.delay)

            except Exception as e:
                st.error(f"Erreur PatentsView: {str(e)}")
                break

        progress_bar.empty()
        status_text.empty()
        return all_patents

class LensFetcher:
    def _init_(self):
        self.api_token = "NKKdKUVJetizjiuFBqyltBQGWg9OWSdtwxJNtcz68FieAHDoX8mc"
        self.base_url = "https://api.lens.org/patent/search"
        self.headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json"
        }

    @staticmethod
    def extract_english_text(field):
        if isinstance(field, list):
            for item in field:
                if isinstance(item, dict) and item.get("lang") == "en":
                    return item.get("text", "")
            return None
        if isinstance(field, dict):
            return None
        return None

    def fetch_patents(self, keyword, total_to_fetch=100, batch_size=25):
        all_patents = []
        progress_bar = st.progress(0)
        status_text = st.empty()

        for offset in range(0, total_to_fetch, batch_size):
            try:
                completion = min((offset + batch_size) / total_to_fetch, 1.0)
                status_text.text(f"Récupération {offset}-{offset+batch_size}... (The Lens)")
                progress_bar.progress(completion)

                payload = {
                    "query": {
                        "match": {"title": keyword}
                    },
                    "size": batch_size,
                    "from": offset,
                    "include": [
                        "biblio.invention_title",
                        "abstract"
                    ]
                }
                response = requests.post(self.base_url, headers=self.headers, json=payload)
                
                if response.status_code != 200:
                    st.error(f"Erreur The Lens (offset={offset}): {response.status_code}")
                    st.code(response.text)
                    break

                data = response.json().get("data", [])
                if not data:
                    break

                for patent in data:
                    title_raw = patent.get("biblio", {}).get("invention_title", [])
                    title_en = self.extract_english_text(title_raw)

                    abstract_raw = patent.get("abstract", [])
                    abstract_en = self.extract_english_text(abstract_raw)

                    if title_en and abstract_en:
                        all_patents.append({
                            "source": "The Lens",
                            "title": title_en,
                            "abstract": abstract_en,
                            "id": patent.get("lens_id", "")
                        })

            except Exception as e:
                st.error(f"Erreur The Lens: {str(e)}")
                break

        progress_bar.empty()
        status_text.empty()
        return all_patents

# ------------ Fonctions PDF ---------------

def save_pv_patents_to_pdf(patents, keyword):
    os.makedirs("data", exist_ok=True)
    safe_keyword = clean_text("".join(c for c in keyword if c.isalnum() or c in (' ', '_')).rstrip())
    filename = os.path.join("data", f"PatentsView_{safe_keyword}.pdf")

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.set_fill_color(200, 220, 255)
    pdf.cell(0, 10, "Résultats PatentsView", ln=True, fill=True)
    pdf.ln(10)
    
    for i, patent in enumerate(patents, 1):
        title = clean_text(patent.get('patent_title', 'Titre non disponible'))
        date = patent.get('patent_date', 'Inconnue')
        pid = patent.get('patent_id', 'Inconnu')
        abstract = clean_text(patent.get('patent_abstract', 'Résumé non disponible'))

        pdf.set_font("Arial", 'B', 12)
        pdf.multi_cell(0, 10, f"{i}. {title}")

        pdf.set_font("Arial", '', 11)
        pdf.cell(0, 8, f"Date: {date} | ID: {pid}", ln=True)
        pdf.multi_cell(0, 8, f"Résumé: {abstract}")
        pdf.ln(8)
    
    pdf.output(filename)
    return filename

def save_lens_patents_to_pdf(patents, keyword):
    os.makedirs("data", exist_ok=True)
    safe_keyword = clean_text("".join(c for c in keyword if c.isalnum() or c in (' ', '_')).rstrip())
    filename = os.path.join("data", f"TheLens_{safe_keyword}.pdf")

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.set_fill_color(220, 255, 220)
    pdf.cell(0, 10, "Résultats The Lens", ln=True, fill=True)
    pdf.ln(10)
    
    for i, patent in enumerate(patents, 1):
        title = clean_text(patent.get('title', 'Titre non disponible'))
        pid = patent.get('id', 'Inconnu')
        abstract = clean_text(patent.get('abstract', 'Résumé non disponible'))

        pdf.set_font("Arial", 'B', 12)
        pdf.multi_cell(0, 10, f"{i}. {title}")

        pdf.set_font("Arial", '', 11)
        pdf.cell(0, 8, f"ID: {pid}", ln=True)
        pdf.multi_cell(0, 8, f"Résumé: {abstract}")
        pdf.ln(8)
    
    pdf.output(filename)
    return filename

# ------------ Pages UI ---------------

def search_page():
    st.title("🔍 Recherche de brevets")
    
    # Initialisation session_state
    if "pv_results" not in st.session_state:
        st.session_state.pv_results = []
    if "lens_results" not in st.session_state:
        st.session_state.lens_results = []
    if "search_in_progress" not in st.session_state:
        st.session_state.search_in_progress = False
    if "search_count" not in st.session_state:
        st.session_state.search_count = 0

    # Barre latérale avec paramètres
    with st.sidebar:
        st.header("Paramètres de recherche")
        keyword = st.text_input("Mot-clé principal:", "artificial intelligence")
        
        st.subheader("PatentsView")
        pv_pages = st.slider("Nombre de pages (100 brevets/page)", 1, 5, 1, key="pv_pages")
        
        st.subheader("The Lens")
        lens_count = st.slider("Nombre de brevets", 25, 200, 100, step=25, key="lens_count")
        
        if st.button("🔎 Lancer la recherche sur les deux sources"):
            st.session_state.search_in_progress = True
            st.session_state.pv_results = []
            st.session_state.lens_results = []
            st.session_state.search_count += 1
            
            # Recherche séquentielle
            with st.spinner("Recherche PatentsView en cours..."):
                fetcher_pv = PatentFetcher()
                patents_pv = fetcher_pv.fetch_patents(
                    keyword=keyword,
                    page_start=1,
                    page_end=pv_pages
                )
                
                st.session_state.pv_results = []
                for patent in patents_pv:
                    st.session_state.pv_results.append({
                        "source": "PatentsView",
                        "title": patent.get("patent_title", "Sans titre"),
                        "abstract": patent.get("patent_abstract", "Non disponible"),
                        "date": patent.get("patent_date", "Inconnue"),
                        "id": patent.get("patent_id", "")
                    })
            
            with st.spinner("Recherche The Lens en cours..."):
                fetcher_lens = LensFetcher()
                patents_lens = fetcher_lens.fetch_patents(
                    keyword=keyword,
                    total_to_fetch=lens_count
                )
                st.session_state.lens_results = patents_lens
            
            st.session_state.search_in_progress = False
            st.rerun()
        
        # Nouveau bouton pour rechercher d'autres résumés
        if st.button("🔄 Rechercher d'autres résumés"):
            st.session_state.search_in_progress = True
            st.session_state.pv_results = []
            st.session_state.lens_results = []
            st.session_state.search_count += 1
            st.rerun()

    # Affichage des résultats
    if st.session_state.search_in_progress:
        st.info("Recherche en cours...")
        return
    
    # Affichage en deux colonnes
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("PatentsView")
        if st.session_state.pv_results:
            st.success(f"✅ {len(st.session_state.pv_results)} brevets trouvés (Recherche #{st.session_state.search_count})")
            for i, patent in enumerate(st.session_state.pv_results, 1):
                with st.expander(f"{i}. {patent['title'][:100]}..."):
                    st.markdown(f"*Date:* {patent.get('date', 'Inconnue')}")
                    st.markdown(f"*ID:* {patent.get('id', 'Inconnu')}")
                    st.markdown("*Résumé:*")
                    st.write(patent["abstract"])
                    
                    if patent.get("id"):
                        st.markdown(f"[🔗 Voir sur Google Patents](https://patents.google.com/patent/US{patent['id']})")
        else:
            st.info("Aucun résultat pour PatentsView")
    
    with col2:
        st.subheader("The Lens")
        if st.session_state.lens_results:
            st.success(f"✅ {len(st.session_state.lens_results)} brevets trouvés (Recherche #{st.session_state.search_count})")
            for i, patent in enumerate(st.session_state.lens_results, 1):
                with st.expander(f"{i}. {patent['title'][:100]}..."):
                    st.markdown(f"*ID:* {patent.get('id', 'Inconnu')}")
                    st.markdown("*Résumé:*")
                    st.write(patent["abstract"])
                    
                    if patent.get("id"):
                        st.markdown(f"[🔗 Voir sur The Lens](https://www.lens.org/lens/patent/{patent['id']})")
        else:
            st.info("Aucun résultat pour The Lens")

    # Actions après recherche
    if st.session_state.pv_results or st.session_state.lens_results:
        st.subheader("Télécharger les résultats")
        
        col_pdf1, col_pdf2 = st.columns(2)
        
        with col_pdf1:
            if st.session_state.pv_results:
                if st.button("📄 Générer PDF PatentsView"):
                    pdf_file = save_pv_patents_to_pdf(
                        st.session_state.pv_results, 
                        keyword
                    )
                    st.success(f"PDF PatentsView généré : {os.path.basename(pdf_file)}")
                    
                    with open(pdf_file, "rb") as f:
                        st.download_button(
                            "📥 Télécharger PDF PatentsView", 
                            f, 
                            file_name=os.path.basename(pdf_file)
                        )
            else:
                st.warning("Aucun résultat PatentsView à exporter")
        
        with col_pdf2:
            if st.session_state.lens_results:
                if st.button("📄 Générer PDF The Lens"):
                    pdf_file = save_lens_patents_to_pdf(
                        st.session_state.lens_results,
                        keyword
                    )
                    st.success(f"PDF The Lens généré : {os.path.basename(pdf_file)}")
                    
                    with open(pdf_file, "rb") as f:
                        st.download_button(
                            "📥 Télécharger PDF The Lens", 
                            f, 
                            file_name=os.path.basename(pdf_file)
                        )
            else:
                st.warning("Aucun résultat The Lens à exporter")
        
        # Bouton pour indexer les résultats dans le chatbot
        if st.button("💬 Indexer dans le chatbot"):
            with st.spinner("Indexation dans la base de connaissances..."):
                # Créer un PDF temporaire combiné pour l'indexation
                combined_text = ""
                
                # Ajouter les résultats PatentsView
                for patent in st.session_state.pv_results:
                    combined_text += f"Titre: {patent['title']}\n"
                    combined_text += f"Date: {patent.get('date', '')}\n"
                    combined_text += f"Résumé: {patent['abstract']}\n\n"
                
                # Ajouter les résultats The Lens
                for patent in st.session_state.lens_results:
                    combined_text += f"Titre: {patent['title']}\n"
                    combined_text += f"Résumé: {patent['abstract']}\n\n"
                
                # Indexer le texte combiné
                splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=100)
                docs = splitter.create_documents([combined_text])
                db = Chroma(persist_directory="chroma", embedding_function=get_embedding_function())
                db.add_documents(docs)
                db.persist()
                st.success("✅ Résultats indexés dans la base persistante du chatbot.")

def chatbot_page():
    st.title("💬 Chatbot - Brevets")

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    st.subheader("📄 Importer un PDF personnel (optionnel)")
    uploaded_file = st.file_uploader("Choisir un fichier PDF", type=["pdf"])

    if uploaded_file:
        st.info("📔 Lecture du fichier PDF...")

        extracted_text = extract_text_from_pdf(uploaded_file)

        if len(extracted_text.strip()) < 50:
            st.error("❌ Impossible d'extraire du texte sélectionnable. Le PDF semble illisible ou scanné.")
        else:
            user_temp_path = os.path.join("chroma_temp", str(uuid.uuid4()))
            os.makedirs(user_temp_path, exist_ok=True)

            splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=100)
            docs = splitter.create_documents([extracted_text])
            db = Chroma(persist_directory=user_temp_path, embedding_function=get_embedding_function())
            db.add_documents(docs)
            db.persist()

            st.session_state["custom_db_path"] = user_temp_path
            st.success("✅ PDF personnel indexé temporairement.")

    if "custom_db_path" in st.session_state:
        if st.button("🧹 Réinitialiser le PDF importé"):
            shutil.rmtree(st.session_state["custom_db_path"], ignore_errors=True)
            del st.session_state["custom_db_path"]
            st.experimental_rerun()

    for sender, message in st.session_state.chat_history:
        with st.chat_message(sender):
            st.markdown(message)

    user_input = st.chat_input("Posez votre question (basée sur le PDF ou les brevets existants)...")

    if user_input:
        with st.chat_message("user"):
            st.markdown(user_input)
        st.session_state.chat_history.append(("user", user_input))

        db_path = st.session_state.get("custom_db_path", "chroma")

        try:
            response = query_rag(user_input, db_path)
        except Exception as e:
            response = f"❌ Une erreur est survenue : {e}"

        with st.chat_message("assistant"):
            st.markdown(response)
        st.session_state.chat_history.append(("assistant", response))

# ------------ Main Application ---------------

def main():
    st.set_page_config(page_title="Patent Assistant Pro", layout="wide")
    
    # Navigation
    page = st.sidebar.selectbox(
        "Navigation", 
        ["🔍 Recherche de brevets", "💬 Chatbot RAG"],
        index=0
    )
    
    if page == "🔍 Recherche de brevets":
        search_page()
    elif page == "💬 Chatbot RAG":
        chatbot_page()

if __name__ == "__main__":
    main()

@atexit.register
def clean_temp_chroma():
    if os.path.exists("chroma_temp"):
        shutil.rmtree("chroma_temp", ignore_errors=True)