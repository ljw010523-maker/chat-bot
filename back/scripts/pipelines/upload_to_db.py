# -*- coding: utf-8 -*-
"""
Chroma Vector Database Uploader
Upload text embeddings and metadata to Chroma DB
"""

import sys
import json
import uuid
import numpy as np
from pathlib import Path
from typing import List, Dict, Optional
import chromadb

# Add project root to path
project_root = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(project_root))


class ChromaUploader:
    """Upload embeddings to Chroma vector database"""

    def __init__(
        self,
        embeddings_folder: str = "data/embeddings",
        chunks_folder: str = "data/chunks",
        chroma_db_path: str = "data/chroma_db",
        collection_name: str = "document_chunks"
    ):
        """
        Args:
            embeddings_folder: Folder containing embedding .npz files
            chunks_folder: Folder containing chunk JSON files with texts
            chroma_db_path: Path to Chroma database
            collection_name: Name of Chroma collection
        """
        self.embeddings_folder = Path(embeddings_folder)
        self.chunks_folder = Path(chunks_folder)
        self.chroma_db_path = Path(chroma_db_path)
        self.collection_name = collection_name

        # Initialize Chroma client
        print(f"\nInitializing Chroma database at: {self.chroma_db_path}")
        self.chroma_db_path.mkdir(parents=True, exist_ok=True)

        self.client = chromadb.PersistentClient(
            path=str(self.chroma_db_path)
        )

        # Create or get collection
        try:
            self.collection = self.client.get_collection(name=collection_name)
            print(f"Collection '{collection_name}' already exists")
            print(f"  Existing documents: {self.collection.count()}")
        except:
            self.collection = self.client.create_collection(
                name=collection_name,
                metadata={"description": "Document chunks with embeddings"}
            )
            print(f"Created new collection: {collection_name}")

    def load_embedding_file(self, embedding_file: Path) -> Optional[np.ndarray]:
        """Load embedding .npz file"""
        try:
            data = np.load(embedding_file)
            embeddings = data['embeddings']
            return embeddings
        except Exception as e:
            print(f"Failed to load embeddings ({embedding_file.name}): {e}")
            return None

    def load_chunk_file(self, chunk_file: Path) -> Optional[Dict]:
        """Load chunk JSON file with texts"""
        try:
            with open(chunk_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data
        except Exception as e:
            print(f"Failed to load chunks ({chunk_file.name}): {e}")
            return None

    def prepare_documents(
        self,
        embeddings: np.ndarray,
        chunk_data: Dict,
        source_file: str
    ) -> Dict:
        """
        Prepare documents for Chroma upload

        Returns:
            Dictionary with ids, embeddings, documents, metadatas
        """
        chunks = chunk_data.get('chunks', [])

        ids = []
        documents = []
        metadatas = []
        embedding_list = []

        for i, chunk in enumerate(chunks):
            if i >= len(embeddings):
                break

            # Generate unique ID
            chunk_id = f"{source_file}_{chunk.get('chunk_id', i)}"
            ids.append(chunk_id)

            # Document text
            text = chunk.get('text', '').strip()
            documents.append(text if text else " ")  # Chroma requires non-empty

            # Metadata
            metadata = {
                "source_file": source_file,
                "chunk_id": chunk.get('chunk_id', i),
                "page_num": chunk.get('page_num', 1),
                "char_count": chunk.get('char_count', 0),
            }

            # Add custom metadata if exists
            if 'metadata' in chunk:
                for key, value in chunk['metadata'].items():
                    metadata[f"custom_{key}"] = str(value)

            metadatas.append(metadata)

            # Embedding
            embedding_list.append(embeddings[i].tolist())

        return {
            "ids": ids,
            "embeddings": embedding_list,
            "documents": documents,
            "metadatas": metadatas
        }

    def upload_to_chroma(self, data: Dict) -> bool:
        """Upload prepared data to Chroma"""
        try:
            self.collection.add(
                ids=data["ids"],
                embeddings=data["embeddings"],
                documents=data["documents"],
                metadatas=data["metadatas"]
            )
            return True
        except Exception as e:
            print(f"Failed to upload to Chroma: {e}")
            return False

    def process_file_pair(
        self,
        embedding_file: Path,
        chunk_file: Path
    ) -> bool:
        """Process a pair of embedding and chunk files"""
        print(f"\n{'='*60}")
        print(f"Processing: {chunk_file.stem}")
        print(f"{'='*60}")

        # 1. Load embeddings
        embeddings = self.load_embedding_file(embedding_file)
        if embeddings is None:
            return False

        print(f"Loaded embeddings: {embeddings.shape}")

        # 2. Load chunks
        chunk_data = self.load_chunk_file(chunk_file)
        if chunk_data is None:
            return False

        total_chunks = len(chunk_data.get('chunks', []))
        print(f"Loaded chunks: {total_chunks}")

        # 3. Prepare documents
        source_file = chunk_data.get('source_file', chunk_file.stem)
        data = self.prepare_documents(embeddings, chunk_data, source_file)

        print(f"Prepared {len(data['ids'])} documents")

        # 4. Upload to Chroma
        if self.upload_to_chroma(data):
            print(f"Successfully uploaded to Chroma!")
            return True
        else:
            return False

    def process_all(self):
        """Process all embedding files"""
        # Find all embedding files
        embedding_files = list(self.embeddings_folder.glob("*_embeddings.npz"))

        if not embedding_files:
            print(f"\nNo embedding files found: {self.embeddings_folder.absolute()}")
            print("Run embed.py first to generate embeddings:")
            print("  python back/scripts/pipelines/embed.py")
            return

        print(f"\n{'='*60}")
        print(f"Chroma Upload Started")
        print(f"{'='*60}")
        print(f"Embeddings folder: {self.embeddings_folder.absolute()}")
        print(f"Chunks folder: {self.chunks_folder.absolute()}")
        print(f"Chroma DB: {self.chroma_db_path.absolute()}")
        print(f"Collection: {self.collection_name}")
        print(f"Files found: {len(embedding_files)}")
        print(f"{'='*60}")

        success_count = 0
        total_documents = 0

        for idx, embedding_file in enumerate(embedding_files, 1):
            print(f"\n[{idx}/{len(embedding_files)}]")

            # Find corresponding chunk file
            # embedding file: "xxx_chunks_embeddings.npz"
            # chunk file: "xxx_chunks.json"
            base_name = embedding_file.stem.replace("_embeddings", "")  # Remove "_embeddings" suffix
            chunk_file = self.chunks_folder / f"{base_name}.json"  # Already has "_chunks"

            if not chunk_file.exists():
                print(f"Warning: Chunk file not found: {chunk_file.name}")
                continue

            try:
                if self.process_file_pair(embedding_file, chunk_file):
                    success_count += 1

                    # Count uploaded documents
                    data = np.load(embedding_file)
                    total_documents += len(data['embeddings'])

            except Exception as e:
                print(f"\nError occurred: {e}")
                import traceback
                traceback.print_exc()

        # Final summary
        print(f"\n{'='*60}")
        print(f"Upload Complete!")
        print(f"{'='*60}")
        print(f"  Success: {success_count}/{len(embedding_files)}")
        print(f"  Failed: {len(embedding_files) - success_count}")
        print(f"  Total documents uploaded: {total_documents}")
        print(f"  Chroma collection: {self.collection_name}")
        print(f"  Total in collection: {self.collection.count()}")
        print(f"  DB location: {self.chroma_db_path.absolute()}")
        print(f"{'='*60}\n")

    def reset_collection(self):
        """Reset (delete and recreate) the collection"""
        try:
            self.client.delete_collection(name=self.collection_name)
            print(f"Deleted collection: {self.collection_name}")
        except:
            pass

        self.collection = self.client.create_collection(
            name=self.collection_name,
            metadata={"description": "Document chunks with embeddings"}
        )
        print(f"Created new collection: {self.collection_name}")


def main():
    """Main execution"""
    import argparse

    parser = argparse.ArgumentParser(description="Upload embeddings to Chroma DB")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Reset (delete) existing collection before upload"
    )
    args = parser.parse_args()

    config = {
        "embeddings_folder": "data/embeddings",
        "chunks_folder": "data/chunks",
        "chroma_db_path": "data/chroma_db",
        "collection_name": "document_chunks"
    }

    print("\n" + "="*60)
    print("Chroma Vector Database Uploader")
    print("="*60)
    print(f"Embeddings: {config['embeddings_folder']}/")
    print(f"Chunks: {config['chunks_folder']}/")
    print(f"Chroma DB: {config['chroma_db_path']}/")
    print(f"Collection: {config['collection_name']}")
    print("="*60)

    try:
        uploader = ChromaUploader(**config)

        if args.reset:
            print("\n⚠️  Resetting collection...")
            uploader.reset_collection()

        uploader.process_all()

    except Exception as e:
        print(f"\nCritical error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
