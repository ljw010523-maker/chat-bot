# -*- coding: utf-8 -*-
"""
LangGraph RAG System
State machine workflow: Retrieve → Grade → Generate
Extensible architecture for complex RAG workflows
"""

import sys
import os
from pathlib import Path
from typing import TypedDict, List
from typing_extensions import Annotated
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add project root to path
project_root = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from langgraph.graph import StateGraph, END
from langchain_chroma import Chroma
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.documents import Document
from sentence_transformers import SentenceTransformer


# Define State
class RAGState(TypedDict):
    """State for RAG workflow"""
    question: str
    context: List[Document]
    answer: str
    grade_passed: bool


class LangGraphRAG:
    """RAG system using LangGraph state machine"""

    def __init__(
        self,
        chroma_db_path: str = "data/chroma_db",
        collection_name: str = "document_chunks",
        model_name: str = "llama-3.3-70b-versatile",
        top_k: int = 5
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

        print(f"\nInitializing LangGraph RAG System...")
        print(f"  Chroma DB: {self.chroma_db_path}")
        print(f"  Collection: {collection_name}")
        print(f"  LLM: {model_name}")
        print(f"  Top-K: {top_k}")

        # Load embedding model
        print("\n  Loading embedding model...")
        self.embedding_model = SentenceTransformer('jhgan/ko-sroberta-multitask')

        # Custom embedding function
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

        # Build workflow
        print("  Building LangGraph workflow...")
        self.workflow = self._build_workflow()
        self.app = self.workflow.compile()

        print("[OK] LangGraph RAG System Ready!\n")

    def _build_workflow(self) -> StateGraph:
        """Build LangGraph workflow"""
        workflow = StateGraph(RAGState)

        # Add nodes
        workflow.add_node("retrieve", self.retrieve_node)
        workflow.add_node("grade", self.grade_node)
        workflow.add_node("generate", self.generate_node)

        # Add edges
        workflow.set_entry_point("retrieve")
        workflow.add_edge("retrieve", "grade")

        # Conditional edge: grade → generate or END
        def decide_after_grade(state: RAGState) -> str:
            if state["grade_passed"]:
                return "generate"
            else:
                return END

        workflow.add_conditional_edges(
            "grade",
            decide_after_grade,
            {
                "generate": "generate",
                END: END
            }
        )

        workflow.add_edge("generate", END)

        return workflow

    def retrieve_node(self, state: RAGState) -> RAGState:
        """Retrieve relevant documents"""
        question = state["question"]

        print(f"\n[RETRIEVE] Searching for: {question[:50]}...")

        # Retrieve documents
        docs = self.vectorstore.similarity_search(
            question,
            k=self.top_k
        )

        print(f"[RETRIEVE] Found {len(docs)} documents")

        return {"context": docs}

    def grade_node(self, state: RAGState) -> RAGState:
        """Grade relevance of retrieved documents"""
        context = state["context"]
        question = state["question"]

        print(f"\n[GRADE] Evaluating {len(context)} documents...")

        # Simple grading: check if we have non-empty documents
        relevant_docs = [doc for doc in context if doc.page_content.strip()]

        if len(relevant_docs) > 0:
            print(f"[GRADE] [OK] {len(relevant_docs)} relevant documents found")
            return {"grade_passed": True, "context": relevant_docs}
        else:
            print(f"[GRADE] ✗ No relevant documents found")
            return {"grade_passed": False, "answer": "I don't have enough information to answer this question."}

    def generate_node(self, state: RAGState) -> RAGState:
        """Generate answer from context"""
        context = state["context"]
        question = state["question"]

        print(f"\n[GENERATE] Generating answer...")

        # Prepare context
        context_text = "\n\n".join([doc.page_content for doc in context])

        # Create prompt
        prompt = ChatPromptTemplate.from_template(
            """You are a helpful assistant that answers questions based on the provided context.

Context:
{context}

Question: {question}

Please provide a clear and concise answer based on the context above. If the answer cannot be found in the context, say "I don't have enough information to answer this question."

Answer in Korean.

Answer:"""
        )

        # Generate answer
        chain = prompt | self.llm
        response = chain.invoke({
            "context": context_text,
            "question": question
        })

        answer = response.content

        print(f"[GENERATE] [OK] Answer generated ({len(answer)} chars)")

        return {"answer": answer}

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
            # Run workflow
            initial_state = RAGState(
                question=question,
                context=[],
                answer="",
                grade_passed=False
            )

            result = self.app.invoke(initial_state)

            answer = result.get("answer", "No answer generated.")
            sources = result.get("context", [])

            print(f"\n{'='*60}")
            print(f"Answer:\n{answer}\n")
            print(f"{'='*60}")

            if sources:
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

    parser = argparse.ArgumentParser(description="LangGraph RAG System")
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
    rag = LangGraphRAG()

    if args.interactive:
        # Interactive mode
        print("\n" + "="*60)
        print("Interactive LangGraph RAG System (type 'exit' to quit)")
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
