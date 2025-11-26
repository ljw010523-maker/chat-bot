# -*- coding: utf-8 -*-
"""
Simple LangChain RAG System
Basic retrieval and generation for document Q&A
"""

import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add project root to path
project_root = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from langchain_chroma import Chroma
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from sentence_transformers import SentenceTransformer


class SimpleRAG:
    """Simple RAG system using LangChain"""

    def __init__(
        self,
        chroma_db_path: str = "data/chroma_db",
        collection_name: str = "document_chunks",
        model_name: str = "llama-3.3-70b-versatile",
        top_k: int = 3
    ):
        """
        Args:
            chroma_db_path: Path to Chroma database
            collection_name: Collection name
            model_name: Groq model name
            top_k: Number of chunks to retrieve
        """
        self.chroma_db_path = Path(chroma_db_path)
        self.collection_name = collection_name
        self.model_name = model_name
        self.top_k = top_k

        # Check API key
        if not os.getenv("GROQ_API_KEY"):
            print("Warning: GROQ_API_KEY environment variable is not set!")
            print("Get your API key at: https://console.groq.com/keys")
            print("Set it with: export GROQ_API_KEY='your-api-key'")
            print("Or in Windows: set GROQ_API_KEY=your-api-key")

        print(f"\nInitializing Simple RAG System...")
        print(f"  Chroma DB: {self.chroma_db_path}")
        print(f"  Collection: {collection_name}")
        print(f"  LLM: {model_name}")
        print(f"  Top-K: {top_k}")

        # Load embedding model (same as used for indexing)
        print("\n  Loading embedding model...")
        self.embedding_model = SentenceTransformer('jhgan/ko-sroberta-multitask')

        # Custom embedding function for Chroma
        class CustomEmbeddings:
            def __init__(self, model):
                self.model = model

            def embed_documents(self, texts):
                return self.model.encode(texts).tolist()

            def embed_query(self, text):
                return self.model.encode([text])[0].tolist()

        self.embeddings = CustomEmbeddings(self.embedding_model)

        # Initialize vector store
        print("  Loading vector store...")
        self.vectorstore = Chroma(
            collection_name=collection_name,
            embedding_function=self.embeddings,
            persist_directory=str(self.chroma_db_path)
        )

        # Initialize LLM
        print("  Initializing LLM...")
        self.llm = ChatGroq(
            model=model_name,
            temperature=0
        )

        # Create custom prompt
        prompt = ChatPromptTemplate.from_template(
            """You are a helpful assistant that answers questions based on the provided context.

Context:
{context}

Question: {question}

Please provide a clear and concise answer based on the context above. If the answer cannot be found in the context, say "I don't have enough information to answer this question."

Answer in Korean.

Answer:"""
        )

        # Create retriever
        print("  Creating RAG chain...")
        self.retriever = self.vectorstore.as_retriever(
            search_kwargs={"k": self.top_k}
        )

        # Format documents function
        def format_docs(docs):
            return "\n\n".join([doc.page_content for doc in docs])

        # Create RAG chain using LCEL
        self.qa_chain = (
            {"context": self.retriever | format_docs, "question": RunnablePassthrough()}
            | prompt
            | self.llm
            | StrOutputParser()
        )

        print("[OK] Simple RAG System Ready!\n")

    def query(self, question: str) -> dict:
        """
        Query the RAG system

        Args:
            question: User question

        Returns:
            Dictionary with answer and source documents
        """
        print(f"\n{'='*60}")
        print(f"Question: {question}")
        print(f"{'='*60}")

        try:
            # Retrieve relevant documents
            sources = self.retriever.invoke(question)

            # Run query to get answer
            answer = self.qa_chain.invoke(question)

            print(f"\nAnswer:\n{answer}\n")
            print(f"\nSources ({len(sources)} documents):")
            for i, doc in enumerate(sources, 1):
                metadata = doc.metadata
                print(f"\n  [{i}] {metadata.get('source_file', 'Unknown')}")
                print(f"      Page: {metadata.get('page_num', 'N/A')}")
                print(f"      Preview: {doc.page_content[:100]}...")

            return {
                "question": question,
                "answer": answer,
                "sources": sources
            }

        except Exception as e:
            print(f"\nError occurred: {e}")
            import traceback
            traceback.print_exc()
            return {
                "question": question,
                "answer": f"Error: {str(e)}",
                "sources": []
            }


def main():
    """Main execution"""
    import argparse

    parser = argparse.ArgumentParser(description="Simple RAG System")
    parser.add_argument(
        "--question",
        "-q",
        type=str,
        help="Question to ask"
    )
    parser.add_argument(
        "--interactive",
        "-i",
        action="store_true",
        help="Run in interactive mode"
    )
    args = parser.parse_args()

    # Initialize RAG system
    rag = SimpleRAG()

    if args.interactive:
        # Interactive mode
        print("\n" + "="*60)
        print("Interactive RAG System (type 'exit' to quit)")
        print("="*60)

        while True:
            try:
                question = input("\nYour question: ").strip()
                if question.lower() in ['exit', 'quit', 'q']:
                    print("Goodbye!")
                    break

                if not question:
                    continue

                rag.query(question)

            except KeyboardInterrupt:
                print("\nGoodbye!")
                break
            except Exception as e:
                print(f"Error: {e}")

    elif args.question:
        # Single question mode
        rag.query(args.question)

    else:
        # Demo mode with example questions
        print("\n" + "="*60)
        print("Demo Mode: Testing with example questions")
        print("="*60)

        example_questions = [
            "회계팀 시스템 수정 요청이 무엇인가요?",
            "시스템 개발 프로젝트 회의록에서 논의된 내용은?",
            "관리자 계정 권한 추가와 관련된 내용은?"
        ]

        for question in example_questions:
            rag.query(question)
            print("\n" + "-"*60)


if __name__ == "__main__":
    main()
