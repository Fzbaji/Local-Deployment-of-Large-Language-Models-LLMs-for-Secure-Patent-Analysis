# Patent Bot : Chatbot d'Analyse de Brevets Local et Sécurisé 🤖🔒

## Introduction

Dans un contexte industriel où l'innovation et la veille technologique sont primordiales, l'analyse des brevets est une tâche stratégique mais complexe et chronophage. L'émergence des Large Language Models (LLMs) offre des perspectives révolutionnaires pour faciliter cette analyse. Cependant, les solutions basées sur le cloud posent un problème majeur de confidentialité des données sensibles, freinant leur adoption dans des environvironnements où la sécurité est non négociable.

**Patent Bot** a été conçu pour répondre à cette problématique. Il s'agit d'un chatbot intelligent d'analyse de brevets, basé sur une architecture RAG (Retrieval-Augmented Generation) et un LLM déployé entièrement en local. 
L'objectif est de fournir une solution performante, précise et surtout, garantissant une confidentialité totale des informations traitées.

## Caractéristiques Principales

**Confidentialité Totale :** Traitement des données 100% en local, sans aucune dépendance au cloud, assurant la conformité au RGPD et la protection des secrets industriels.

**Analyse Intelligente :** Utilisation d'une architecture RAG pour des réponses précises et contextualisées basées sur les documents de brevets.


**Flexibilité d'Acquisition :** Possibilité d'uploader manuellement des PDF ou de collecter automatiquement des résumés de brevets via les APIs PatentsView et The Lens.
**Modèles Open-Source :** Support de LLMs locaux comme LLaMA3.2 et Mistral via Ollama.

**Interface Utilisateur Intuitive :** Développé avec Streamlit pour une expérience utilisateur fluide.

## Architecture (Pipeline & Workflow)

Le fonctionnement de Patent Bot repose sur un pipeline structuré en plusieurs étapes clés :

1.  **Acquisition des Données :**
    Recherche automatisée de résumés de brevets par mots-clés via les APIs PatentsView et The Lens, convertis en PDF.
    Upload manuel de fichiers PDF de brevets par l'utilisateur.
2.  **Prétraitement des Fichiers :** Extraction du texte brut, découpage en "chunks" avec chevauchement pour maintenir le contexte.
3.  **Indexation Vectorielle :** Génération d'embeddings (mxbai-embed-large) et stockage dans une base vectorielle locale (ChromaDB).
4.  **Interface Utilisateur & RAG :** L'utilisateur pose une question, une recherche sémantique récupère les passages pertinents, et un LLM local génère la réponse basée sur ce contexte.
5.  **Suivi du Dialogue :** L'historique des interactions est conservé pour une meilleure continuité.

## Technologies Utilisées

* **Frameworks :**
    [Streamlit](https://streamlit.io/) : Pour l'interface utilisateur web interactive.
    [LangChain](https://www.langchain.com/) : Pour orchestrer le pipeline RAG et gérer les interactions avec le LLM et la base vectorielle.
* **Bases de Données Vectorielles :**
    [ChromaDB](https://www.trychroma.com/) : Base vectorielle locale pour le stockage efficace des embeddings.
* **Modèles de Langage (LLMs) & Exécution Locale :**
    [Ollama](https://ollama.com/) : Pour l'exécution des LLMs (LLaMA3.2, Mistral) en local.
* **Bibliothèques Python :**
    `pdfplumber` / `PyPDF2` : Pour l'extraction de texte à partir de PDFs.
    `PyMuPDF (fitz)` : Pour une extraction efficace du texte brut.
* **APIs Externes (pour la collecte initiale) :**
    * [PatentsView API](https://www.patentsview.org/api/data.html)
    * [The Lens API](https://www.lens.org/lens/search/patents)

## Résultats et Performances

Nos tests ont démontré que Patent Bot offre un excellent compromis entre performance et confidentialité :

**Qualité des Réponses :** Les modèles locaux (LLaMA3.2, Mistral) fournissent des réponses correctes, pertinentes et fiables, comparables à celles de solutions cloud pour la pertinence contextuelle.

**Rapidité des Réponses :** Les temps de réponse varient de 45 à 70 secondes pour la solution locale, ce qui est très satisfaisant pour un usage interactif compte tenu du traitement entièrement local.

**Sécurité :** L'architecture 100% locale garantit une confidentialité totale des données, un contrôle complet et une conformité RGPD simplifiée, contrairement aux solutions cloud.

## Comment Utiliser Patent Bot (Guide Rapide)

1.  **Cloner le dépôt :**
    ```bash
    git clone 
    [Local-Deployment-of-Large-Language-Models-LLMs-for-Secure-Patent-Analysis](https://github.com/Fzbaji/Local-Deployment-of-Large-Language-Models-LLMs-for-Secure-Patent-Analysis.git)
    
    ```
2.  **Installer Ollama et télécharger les modèles :**
    * Suivez les instructions sur [ollama.com](https://ollama.com/) pour installer Ollama.
    * Téléchargez les modèles que vous souhaitez utiliser (ex: Llama3.2 ou Mistral) :
        ```bash
        ollama pull llama3.2
        ollama pull mistral
        ```
3.  **Créer un environnement virtuel et installer les dépendances :**
    ```bash
    python -m venv venv
    source venv/bin/activate  # Sur Linux/macOS
    # venv\Scripts\activate  # Sur Windows
    pip install -r requirements.txt
    ```
    
4.  **Lancer l'application Streamlit :**
    ```bash
    streamlit run PatentBot_PatentView_api.py
    ```

---
