"""Memory system tools for storing and retrieving past solutions."""

from typing import List, Dict, Any, Optional
from datetime import datetime
import json
from pathlib import Path

from autogen_core import CancellationToken
from autogen_agentchat.base import TaskResult
from autogen_ext.tools import BaseTool
from pydantic import BaseModel, Field
import chromadb
from chromadb.config import Settings as ChromaSettings
from autogen_ext.models.openai import OpenAIChatCompletionClient

from ..config import settings


class MemoryStoreInput(BaseModel):
    """Input for storing in memory."""
    content: str = Field(description="Content to store")
    metadata: Dict[str, Any] = Field(description="Metadata about the content")
    category: str = Field(default="solution", description="Category of memory")
    
    
class MemoryStoreResult(BaseModel):
    """Result from memory storage."""
    memory_id: str = Field(description="ID of stored memory")
    success: bool = Field(description="Whether storage was successful")


class MemorySearchInput(BaseModel):
    """Input for searching memory."""
    query: str = Field(description="Search query")
    category: Optional[str] = Field(default=None, description="Filter by category")
    max_results: int = Field(default=5, description="Maximum number of results")
    similarity_threshold: float = Field(default=0.7, description="Minimum similarity score")


class MemorySearchResult(BaseModel):
    """Result from memory search."""
    results: List[Dict[str, Any]] = Field(description="Search results with content and metadata")
    total_results: int = Field(description="Total number of results found")


class MemorySearchTool(BaseTool[MemorySearchInput, MemorySearchResult]):
    """Tool for searching past solutions and experiences."""
    
    def __init__(self):
        super().__init__(
            name="search_memory",
            description="Search for similar past solutions and debugging experiences"
        )
        self.chroma_client = None
        self.collection = None
        self.embedding_client = None
        
    def _get_chroma_client(self):
        """Get or create ChromaDB client."""
        if self.chroma_client is None:
            persist_dir = Path(settings.memory.persist_directory)
            persist_dir.mkdir(parents=True, exist_ok=True)
            
            self.chroma_client = chromadb.PersistentClient(
                path=str(persist_dir),
                settings=ChromaSettings(
                    anonymized_telemetry=False,
                    allow_reset=True
                )
            )
            
            # Get or create collection
            try:
                self.collection = self.chroma_client.get_collection(
                    name=settings.memory.collection_name
                )
            except:
                self.collection = self.chroma_client.create_collection(
                    name=settings.memory.collection_name,
                    metadata={"hnsw:space": "cosine"}
                )
                
        return self.chroma_client, self.collection
    
    def _get_embedding_client(self):
        """Get or create embedding client."""
        if self.embedding_client is None:
            self.embedding_client = OpenAIChatCompletionClient(
                model=settings.memory.embedding_model,
                api_key=settings.planner_model.api_key
            )
        return self.embedding_client
    
    async def _get_embedding(self, text: str) -> List[float]:
        """Get embedding for text."""
        client = self._get_embedding_client()
        
        # Use OpenAI embeddings API
        import openai
        openai.api_key = settings.planner_model.api_key
        
        response = await openai.embeddings.create(
            model=settings.memory.embedding_model,
            input=text
        )
        
        return response.data[0].embedding
    
    async def run(
        self,
        args: MemorySearchInput,
        cancellation_token: CancellationToken
    ) -> TaskResult[MemorySearchResult]:
        """Search memory for similar content."""
        try:
            _, collection = self._get_chroma_client()
            
            # Get embedding for query
            query_embedding = await self._get_embedding(args.query)
            
            # Build where clause for filtering
            where = {}
            if args.category:
                where["category"] = args.category
            
            # Search collection
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=args.max_results,
                where=where if where else None,
                include=["metadatas", "documents", "distances"]
            )
            
            # Format results
            formatted_results = []
            if results['ids'] and len(results['ids'][0]) > 0:
                for i in range(len(results['ids'][0])):
                    # Calculate similarity score (1 - distance for cosine)
                    similarity = 1 - results['distances'][0][i]
                    
                    if similarity >= args.similarity_threshold:
                        formatted_results.append({
                            "id": results['ids'][0][i],
                            "content": results['documents'][0][i],
                            "metadata": results['metadatas'][0][i],
                            "similarity": similarity
                        })
            
            return TaskResult(
                MemorySearchResult(
                    results=formatted_results,
                    total_results=len(formatted_results)
                ),
                task_result_type="MemorySearchResult"
            )
            
        except Exception as e:
            return TaskResult(
                MemorySearchResult(results=[], total_results=0),
                error=str(e)
            )


class MemoryStoreTool(BaseTool[MemoryStoreInput, MemoryStoreResult]):
    """Tool for storing solutions and experiences in memory."""
    
    def __init__(self):
        super().__init__(
            name="store_memory",
            description="Store debugging solutions and experiences for future reference"
        )
        self.search_tool = MemorySearchTool()
    
    async def run(
        self,
        args: MemoryStoreInput,
        cancellation_token: CancellationToken
    ) -> TaskResult[MemoryStoreResult]:
        """Store content in memory."""
        try:
            _, collection = self.search_tool._get_chroma_client()
            
            # Get embedding for content
            embedding = await self.search_tool._get_embedding(args.content)
            
            # Generate ID
            from uuid import uuid4
            memory_id = str(uuid4())
            
            # Add timestamp to metadata
            metadata = args.metadata.copy()
            metadata["category"] = args.category
            metadata["stored_at"] = datetime.utcnow().isoformat()
            
            # Store in collection
            collection.add(
                ids=[memory_id],
                embeddings=[embedding],
                documents=[args.content],
                metadatas=[metadata]
            )
            
            return TaskResult(
                MemoryStoreResult(
                    memory_id=memory_id,
                    success=True
                ),
                task_result_type="MemoryStoreResult"
            )
            
        except Exception as e:
            return TaskResult(
                MemoryStoreResult(memory_id="", success=False),
                error=str(e)
            )