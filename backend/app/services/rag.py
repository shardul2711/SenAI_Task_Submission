import os
import re
from app.services.vector_store import LocalVectorStore
from openai import OpenAI
from app.config import settings

class RAGService:
    def __init__(self):
        # Initialize custom NumPy vector database client
        self.collection = LocalVectorStore(persist_dir=settings.CHROMA_PERSIST_DIR)
        
        # Initialize OpenAI Client
        self.openai_client = None
        key = settings.OPENAI_API_KEY.strip() if settings.OPENAI_API_KEY else ""
        if key and key not in ("YOUR_OPENAI_API_KEY", "your_openai_key", "") and not key.startswith("YOUR_") and not key.startswith("your_"):
            self.openai_client = OpenAI(api_key=key)

    def get_openai_client(self):
        if not self.openai_client:
            key = settings.OPENAI_API_KEY.strip() if settings.OPENAI_API_KEY else ""
            if key and key not in ("YOUR_OPENAI_API_KEY", "your_openai_key", "") and not key.startswith("YOUR_") and not key.startswith("your_"):
                if key.startswith("gsk_"):
                    self.openai_client = OpenAI(api_key=key, base_url="https://api.groq.com/openai/v1")
                else:
                    self.openai_client = OpenAI(api_key=key)
        return self.openai_client

    def get_embedding(self, text: str) -> list:
        key = settings.OPENAI_API_KEY.strip() if settings.OPENAI_API_KEY else ""
        if key.startswith("gsk_") or not self.get_openai_client():
            # Groq does not support embeddings; generate deterministic Random Indexing vectors locally
            import hashlib
            import numpy as np
            dim = 1536
            words = re.findall(r'\b\w+\b', text.lower())
            if not words:
                return [0.0] * dim
            vec = np.zeros(dim)
            for word in words:
                seed = int(hashlib.md5(word.encode('utf-8')).hexdigest(), 16) % (2**32)
                vec += np.random.RandomState(seed).randn(dim)
            norm = np.linalg.norm(vec)
            if norm > 0:
                vec = vec / norm
            return vec.tolist()
        
        try:
            client = self.get_openai_client()
            response = client.embeddings.create(
                input=[text.replace("\n", " ")],
                model="text-embedding-3-small"
            )
            return response.data[0].embedding
        except Exception as e:
            print(f"OpenAI embedding generation failed: {e}. Falling back to local Random Indexing.")
            import hashlib
            import numpy as np
            dim = 1536
            words = re.findall(r'\b\w+\b', text.lower())
            if not words:
                return [0.0] * dim
            vec = np.zeros(dim)
            for word in words:
                seed = int(hashlib.md5(word.encode('utf-8')).hexdigest(), 16) % (2**32)
                vec += np.random.RandomState(seed).randn(dim)
            norm = np.linalg.norm(vec)
            if norm > 0:
                vec = vec / norm
            return vec.tolist()

    def chunk_text(self, text: str, chunk_size: int = 1500, overlap: int = 200) -> list:
        """
        Splits text into chunks of character size roughly matching 300-500 tokens.
        """
        chunks = []
        start = 0
        text_len = len(text)
        
        while start < text_len:
            end = min(start + chunk_size, text_len)
            # Try to align end to paragraph or sentence boundary
            if end < text_len:
                # search backwards for newline or period
                boundary = -1
                for i in range(end, max(start, end - 150), -1):
                    if text[i] == '\n':
                        boundary = i
                        break
                    elif text[i] in ['.', '!', '?'] and text[i-1].islower():
                        boundary = i + 1
                        break
                if boundary != -1:
                    end = boundary
            
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            
            start = end - overlap
            if start >= text_len or end == text_len:
                break
                
        return chunks

    def seed_knowledge_base(self, kb_dir: str, db_session = None):
        """
        Loads markdown documents from kb_dir, chunks them, generates embeddings,
        saves to ChromaDB and also metadata in MySQL knowledge_chunks if db_session is provided.
        """
        if not os.path.exists(kb_dir):
            print(f"Knowledge base directory {kb_dir} not found.")
            return
            
        files = [f for f in os.listdir(kb_dir) if f.endswith(".md")]
        if not files:
            print("No markdown files found to seed.")
            return

        print(f"Found {len(files)} files to seed in RAG vector database.")
        
        # Clear existing elements first to make seeding idempotent
        try:
            # We can delete all items
            existing = self.collection.get()
            if existing and existing['ids']:
                self.collection.delete(ids=existing['ids'])
        except Exception as e:
            print(f"Error resetting collection: {e}")

        chunk_id_counter = 1
        for filename in files:
            file_path = os.path.join(kb_dir, filename)
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            
            chunks = self.chunk_text(content)
            print(f"File {filename} split into {len(chunks)} chunks.")
            
            for idx, chunk in enumerate(chunks):
                doc_id = f"chunk_{filename[:-3]}_{idx}"
                
                # Generate embedding
                embedding = self.get_embedding(chunk)
                
                # Add to ChromaDB
                self.collection.add(
                    ids=[doc_id],
                    embeddings=[embedding],
                    metadatas=[{"source_doc": filename}],
                    documents=[chunk]
                )
                
                # Add to MySQL if session is active
                if db_session:
                    from app.models import KnowledgeChunk
                    db_chunk = KnowledgeChunk(
                        source_doc=filename,
                        chunk_text=chunk
                    )
                    db_session.add(db_chunk)
                    
                chunk_id_counter += 1
                
        if db_session:
            db_session.commit()
            print("Seeded database knowledge_chunks and ChromaDB vectors successfully.")

    def search(self, query: str, top_k: int = 3) -> list:
        """
        Returns top_k relevant chunks with source_doc, chunk text, and similarity score.
        """
        query_embedding = self.get_embedding(query)
        
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k
        )
        
        formatted_results = []
        if results and results["ids"] and results["ids"][0]:
            for i in range(len(results["ids"][0])):
                # Calculate similarity score. Chroma by default returns L2 distance.
                # Cosine similarity can be inferred or we can show L2 distance.
                # Let's convert L2 distance to a standard similarity score.
                distance = results["distances"][0][i]
                # Sim = 1 / (1 + distance) or similar
                similarity = round(1.0 / (1.0 + distance), 4)
                
                formatted_results.append({
                    "id": results["ids"][0][i],
                    "source_doc": results["metadatas"][0][i]["source_doc"],
                    "chunk": results["documents"][0][i],
                    "score": similarity
                })
                
        return formatted_results

rag_service = RAGService()
