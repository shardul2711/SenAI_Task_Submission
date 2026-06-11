import os
import json
import numpy as np

class LocalVectorStore:
    def __init__(self, persist_dir: str):
        self.persist_dir = persist_dir
        self.index_file = os.path.join(persist_dir, "vector_index.json")
        os.makedirs(persist_dir, exist_ok=True)
        self.data = self._load()

    def _load(self) -> dict:
        if os.path.exists(self.index_file):
            try:
                with open(self.index_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading vector index: {e}")
                return {}
        return {}

    def save(self):
        try:
            with open(self.index_file, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2)
        except Exception as e:
            print(f"Error saving vector index: {e}")

    def add(self, ids: list, embeddings: list, metadatas: list, documents: list):
        for i, doc_id in enumerate(ids):
            self.data[doc_id] = {
                "embedding": embeddings[i],
                "metadata": metadatas[i],
                "document": documents[i]
            }
        self.save()

    def query(self, query_embeddings: list, n_results: int = 3) -> dict:
        if not self.data:
            return {
                "ids": [[]],
                "distances": [[]],
                "metadatas": [[]],
                "documents": [[]]
            }
            
        query_vec = np.array(query_embeddings[0])
        results = []
        
        for doc_id, item in self.data.items():
            doc_vec = np.array(item["embedding"])
            # Calculate L2 distance (squared sum of differences)
            diff = query_vec - doc_vec
            dist = np.sum(diff ** 2)
            results.append((dist, doc_id, item["metadata"], item["document"]))
            
        # Sort by distance (closest first)
        results.sort(key=lambda x: x[0])
        top_results = results[:n_results]
        
        ret = {
            "ids": [[]],
            "distances": [[]],
            "metadatas": [[]],
            "documents": [[]]
        }
        
        for dist, doc_id, metadata, document in top_results:
            ret["ids"][0].append(doc_id)
            ret["distances"][0].append(float(dist))
            ret["metadatas"][0].append(metadata)
            ret["documents"][0].append(document)
            
        return ret

    def get(self) -> dict:
        return {
            "ids": list(self.data.keys())
        }

    def delete(self, ids: list):
        for doc_id in ids:
            if doc_id in self.data:
                del self.data[doc_id]
        self.save()
