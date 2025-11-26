# -*- coding: utf-8 -*-
"""
Vector Embedding Generator
Korean-optimized embedding generation using jhgan/ko-sroberta-multitask
"""

import sys
import json
import numpy as np
from pathlib import Path
from typing import List, Dict, Optional
from sentence_transformers import SentenceTransformer

# Add project root to path
project_root = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(project_root))


class EmbeddingGenerator:
    """Generate vector embeddings from text chunks"""

    def __init__(
        self,
        model_name: str = "jhgan/ko-sroberta-multitask",
        chunks_folder: str = "data/chunks",
        output_folder: str = "data/embeddings"
    ):
        """
        Args:
            model_name: Embedding model (default: Korean-optimized)
            chunks_folder: Input folder with chunk JSON files
            output_folder: Folder to save embedding results
        """
        self.model_name = model_name
        self.chunks_folder = Path(chunks_folder)
        self.output_folder = Path(output_folder)
        self.output_folder.mkdir(parents=True, exist_ok=True)

        # Load embedding model
        print(f"\nLoading embedding model: {model_name}")
        self.model = SentenceTransformer(model_name)
        print(f"Model loaded successfully!")
        print(f"   - Model: {model_name}")
        print(f"   - Embedding dimension: {self.model.get_sentence_embedding_dimension()}")

    def load_chunk_file(self, chunk_file: Path) -> Optional[Dict]:
        """Load chunk JSON file"""
        try:
            with open(chunk_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data
        except Exception as e:
            print(f"Failed to load file ({chunk_file.name}): {e}")
            return None

    def extract_texts(self, chunk_data: Dict) -> List[str]:
        """Extract texts from chunk data"""
        texts = []
        chunks = chunk_data.get('chunks', [])

        for chunk in chunks:
            text = chunk.get('text', '').strip()
            if text:
                texts.append(text)
            else:
                texts.append("")  # Keep empty string to maintain index alignment

        return texts

    def generate_embeddings(self, texts: List[str], batch_size: int = 32) -> np.ndarray:
        """
        Convert text list to vector embeddings

        Args:
            texts: List of texts
            batch_size: Batch size (reduce if memory constrained)

        Returns:
            numpy array (shape: [num_texts, embedding_dim])
        """
        if not texts:
            return np.array([])

        print(f"   Generating embeddings... (total {len(texts)} chunks)")

        try:
            # Generate embeddings with batch processing
            embeddings = self.model.encode(
                texts,
                batch_size=batch_size,
                show_progress_bar=True,
                convert_to_numpy=True
            )

            # Handle empty texts with zero vectors
            for i, text in enumerate(texts):
                if not text.strip():
                    embeddings[i] = np.zeros_like(embeddings[i])

            print(f"   Embeddings generated successfully!")
            print(f"      - Shape: {embeddings.shape}")
            print(f"      - Dimension: {embeddings.shape[1]}D")

            return embeddings

        except Exception as e:
            print(f"   Failed to generate embeddings: {e}")
            return np.array([])

    def save_embeddings(
        self,
        embeddings: np.ndarray,
        chunk_data: Dict,
        output_name: str
    ):
        """
        Save embeddings and metadata

        File format:
        - {output_name}_embeddings.npz: Vector data (compressed numpy)
        - {output_name}_embeddings.json: Metadata (chunk information)
        """
        # 1. Save vectors (numpy compressed)
        vector_path = self.output_folder / f"{output_name}_embeddings.npz"
        np.savez_compressed(vector_path, embeddings=embeddings)

        # 2. Save metadata (JSON)
        metadata = {
            "source_file": chunk_data.get("source_file", "unknown"),
            "file_type": chunk_data.get("file_type", ""),
            "total_chunks": len(chunk_data.get("chunks", [])),
            "embedding_dim": embeddings.shape[1] if len(embeddings) > 0 else 0,
            "model_name": self.model_name,
            "chunks": []
        }

        # Add chunk info (metadata only, excluding text)
        for i, chunk in enumerate(chunk_data.get("chunks", [])):
            chunk_meta = {
                "chunk_id": chunk.get("chunk_id", i),
                "page_num": chunk.get("page_num", 1),
                "char_count": chunk.get("char_count", 0),
                "has_embedding": i < len(embeddings),
            }

            # Add additional metadata
            if "metadata" in chunk:
                chunk_meta["metadata"] = chunk["metadata"]

            metadata["chunks"].append(chunk_meta)

        metadata_path = self.output_folder / f"{output_name}_embeddings.json"
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

        print(f"   Saved:")
        print(f"      - Vectors: {vector_path}")
        print(f"      - Metadata: {metadata_path}")

    def process_chunk_file(self, chunk_file: Path) -> bool:
        """Process single chunk file"""
        print(f"\n{'='*60}")
        print(f"Processing: {chunk_file.name}")
        print(f"{'='*60}")

        # 1. Load chunk file
        chunk_data = self.load_chunk_file(chunk_file)
        if not chunk_data:
            return False

        total_chunks = len(chunk_data.get('chunks', []))
        print(f"Total chunks: {total_chunks}")

        # 2. Extract texts
        texts = self.extract_texts(chunk_data)
        non_empty = sum(1 for t in texts if t.strip())
        print(f"Non-empty chunks: {non_empty}")

        if non_empty == 0:
            print("Warning: No text to embed.")
            return False

        # 3. Generate embeddings
        embeddings = self.generate_embeddings(texts)
        if len(embeddings) == 0:
            return False

        # 4. Save results
        output_name = chunk_file.stem  # Remove extension
        self.save_embeddings(embeddings, chunk_data, output_name)

        return True

    def process_all(self):
        """Process all chunk files in folder"""
        # Process only files ending with _chunks.json (exclude privacy_report)
        chunk_files = list(self.chunks_folder.glob("*_chunks.json"))

        if not chunk_files:
            print(f"\nNo chunk files found: {self.chunks_folder.absolute()}")
            print("Run pipeline first to generate chunks:")
            print("  python back/scripts/pipelines/ocr_and_clean.py")
            return

        print(f"\n{'='*60}")
        print(f"Vector Embedding Generation Started")
        print(f"{'='*60}")
        print(f"Chunks folder: {self.chunks_folder.absolute()}")
        print(f"Files found: {len(chunk_files)}")
        print(f"Embedding model: {self.model_name}")
        print(f"{'='*60}")

        success_count = 0
        total_embeddings = 0

        for idx, chunk_file in enumerate(chunk_files, 1):
            print(f"\n[{idx}/{len(chunk_files)}]")
            try:
                if self.process_chunk_file(chunk_file):
                    success_count += 1

                    # Check number of saved embeddings
                    output_name = chunk_file.stem
                    vector_path = self.output_folder / f"{output_name}_embeddings.npz"
                    if vector_path.exists():
                        data = np.load(vector_path)
                        total_embeddings += len(data['embeddings'])

            except Exception as e:
                print(f"\nError occurred: {e}")
                import traceback
                traceback.print_exc()

        # Final summary
        print(f"\n{'='*60}")
        print(f"Embedding Generation Complete!")
        print(f"{'='*60}")
        print(f"  Success: {success_count}/{len(chunk_files)}")
        print(f"  Failed: {len(chunk_files) - success_count}")
        print(f"  Total embeddings generated: {total_embeddings}")
        print(f"  Output location: {self.output_folder.absolute()}")
        print(f"{'='*60}\n")


def main():
    """Main execution"""
    # Default configuration
    config = {
        "model_name": "jhgan/ko-sroberta-multitask",  # Korean optimized model
        "chunks_folder": "data/chunks",
        "output_folder": "data/embeddings"
    }

    print("\n" + "="*60)
    print("Vector Embedding Generator")
    print("="*60)
    print(f"Model: {config['model_name']}")
    print(f"Input: {config['chunks_folder']}/")
    print(f"Output: {config['output_folder']}/")
    print("="*60)

    try:
        generator = EmbeddingGenerator(**config)
        generator.process_all()
    except Exception as e:
        print(f"\nCritical error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
