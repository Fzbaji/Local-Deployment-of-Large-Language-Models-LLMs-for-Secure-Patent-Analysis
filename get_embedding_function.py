from langchain_community.embeddings.ollama import OllamaEmbeddings  # Pour Bedrock

def get_embedding_function():
    
    return OllamaEmbeddings(model="mxbai-embed-large:latest")
