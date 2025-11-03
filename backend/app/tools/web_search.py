"""Web search workflow: MCP → LangChain Tavily → SDK fallback."""

from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass
from typing import List, Optional

import aiohttp

from ..config import settings
from ..logger import get_logger
from .dspy_pipeline import SearchResult, WebDocument

logger = get_logger(__name__)


@dataclass
class MCPDocument:
    id: str
    title: str
    url: str
    snippet: str
    score: float


async def _parse_tavily_response(result: dict) -> List[MCPDocument]:
    """Parse Tavily API response into MCPDocument objects."""
    documents: List[MCPDocument] = []
    
    # Handle both direct results and nested results
    results_list = result.get("results", [])
    if not results_list and isinstance(result, list):
        results_list = result
    
    for idx, item in enumerate(results_list):
        documents.append(
            MCPDocument(
                id=item.get("id", str(idx)),
                title=item.get("title", "Untitled"),
                url=item.get("url", ""),
                snippet=item.get("content", ""),
                score=item.get("score", 0.0),
            )
        )
    return documents


async def _invoke_mcp_tavily(query: str, max_results: int = 5) -> List[MCPDocument]:
    """Invoke Tavily via MCP server with multiple payload format attempts."""
    mcp_url = settings.mcp_tavily_url or os.getenv("MCP_TAVILY_URL")
    
    if not mcp_url:
        logger.debug("web_search.mcp_not_configured")
        raise RuntimeError("MCP URL not configured")
    
    # Try different payload formats that MCP servers commonly use
    payload_formats = [
        # Format 1: MCP protocol with tools/call
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "tavily_search",
                "arguments": {
                    "query": query,
                    "max_results": max_results
                }
            }
        },
        # Format 2: Direct tavily_search method
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tavily_search",
            "params": {
                "query": query,
                "max_results": max_results
            }
        },
        # Format 3: Call tool method
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "call_tool",
            "params": {
                "name": "tavily_search",
                "arguments": {
                    "query": query,
                    "max_results": max_results
                }
            }
        },
    ]
    
    last_error = None
    
    async with aiohttp.ClientSession() as session:
        # Quick health check
        try:
            async with session.head(mcp_url, timeout=10) as health_resp:
                if health_resp.status not in (200, 405):  # 405 = Method Not Allowed for HEAD
                    logger.warning("web_search.mcp_health_check_failed", 
                                 status=health_resp.status)
        except Exception as health_exc:
            logger.warning("web_search.mcp_unreachable", 
                         error=str(health_exc),
                         url=mcp_url)
            raise RuntimeError(f"MCP server unreachable: {health_exc}")
        
        # Try each payload format
        for idx, payload in enumerate(payload_formats, 1):
            try:
                logger.debug("web_search.mcp_attempting_format", 
                           format_number=idx,
                           method=payload.get("method"))
                
                headers = {
                    "Accept": "text/event-stream, application/json",
                    "Content-Type": "application/json",
                }
                
                async with session.post(mcp_url, headers=headers, json=payload, timeout=30) as resp:
                    ctype = resp.headers.get("Content-Type", "")
                    status = resp.status
                    
                    if status != 200:
                        response_text = await resp.text()
                        logger.debug("web_search.mcp_format_failed", 
                                   format_number=idx,
                                   status=status,
                                   response=response_text[:200])
                        last_error = f"HTTP {status}: {response_text[:100]}"
                        continue
                    
                    # Handle SSE response
                    if "text/event-stream" in ctype:
                        last_json = None
                        async for raw in resp.content:
                            line = raw.decode("utf-8", errors="ignore").strip()
                            if line.startswith("data:"):
                                data_str = line[5:].strip()
                                if data_str and data_str != "[DONE]":
                                    last_json = data_str
                        
                        if not last_json:
                            logger.debug("web_search.mcp_empty_sse", format_number=idx)
                            last_error = "Empty SSE stream"
                            continue
                        
                        data = json.loads(last_json)
                    else:
                        # Handle JSON response
                        data = await resp.json()
                    
                    # Check for JSON-RPC error
                    if "error" in data:
                        error_detail = data["error"]
                        logger.debug("web_search.mcp_format_error", 
                                   format_number=idx,
                                   error=error_detail)
                        last_error = f"RPC error: {error_detail}"
                        continue
                    
                    # Extract result
                    result = data.get("result", {})
                    
                    # Handle MCP protocol response format
                    if "content" in result and isinstance(result["content"], list):
                        for content_item in result["content"]:
                            if content_item.get("type") == "text":
                                text_data = content_item.get("text", "")
                                try:
                                    tavily_result = json.loads(text_data)
                                    documents = await _parse_tavily_response(tavily_result)
                                    if documents:
                                        logger.info("web_search.mcp_success", 
                                                  format_number=idx,
                                                  document_count=len(documents))
                                        return documents
                                except json.JSONDecodeError:
                                    continue
                    
                    # Handle direct Tavily response format
                    if "results" in result:
                        documents = await _parse_tavily_response(result)
                        if documents:
                            logger.info("web_search.mcp_success", 
                                      format_number=idx,
                                      document_count=len(documents))
                            return documents
                    
                    last_error = f"No results in response structure: {list(result.keys())}"
                    
            except asyncio.TimeoutError:
                logger.debug("web_search.mcp_timeout", format_number=idx)
                last_error = "Request timeout"
                continue
            except Exception as exc:
                logger.debug("web_search.mcp_format_exception", 
                           format_number=idx,
                           error=str(exc),
                           error_type=type(exc).__name__)
                last_error = str(exc)
                continue
    
    # All formats failed
    logger.warning("web_search.mcp_all_formats_failed", 
                  last_error=last_error,
                  formats_tried=len(payload_formats))
    raise RuntimeError(f"MCP failed: {last_error}")


# LangChain Tavily tool (preferred fallback)
try:
    from langchain_tavily import TavilySearch  # type: ignore
except Exception:
    TavilySearch = None  # type: ignore


async def _run_tavily_langchain(query: str, max_results: int = 5) -> List[MCPDocument]:
    """Use LangChain Tavily tool - the recommended integration."""
    if TavilySearch is None:
        raise RuntimeError("LangChain Tavily not installed. Run: pip install -U langchain-tavily")
    
    if not settings.tavily_api_key:
        raise RuntimeError("TAVILY_API_KEY not configured")
    
    # Ensure API key is in environment for LangChain
    os.environ["TAVILY_API_KEY"] = settings.tavily_api_key
    
    try:
        # Initialize the tool with recommended settings
        tool = TavilySearch(
            max_results=max_results,
            topic="general",
            search_depth="basic",
        )
        
        # Invoke the tool - it returns a dict with results
        result = await asyncio.to_thread(tool.invoke, {"query": query})
        
        documents: List[MCPDocument] = []
        results_list = result.get("results", [])
        
        for idx, item in enumerate(results_list):
            documents.append(
                MCPDocument(
                    id=item.get("id", str(idx)),
                    title=item.get("title", "Untitled"),
                    url=item.get("url", ""),
                    snippet=item.get("content", ""),
                    score=item.get("score", 0.0),
                )
            )
        
        return documents
        
    except Exception as exc:
        logger.error("web_search.langchain_execution_error", 
                    error=str(exc),
                    error_type=type(exc).__name__)
        raise RuntimeError(f"LangChain Tavily failed: {exc}")


# Direct Tavily SDK (last resort fallback)
try:
    from tavily import TavilyClient  # type: ignore
except Exception:
    TavilyClient = None  # type: ignore


async def _run_tavily_sdk(query: str, max_results: int = 5) -> List[MCPDocument]:
    """Direct Tavily SDK as last resort fallback."""
    if TavilyClient is None:
        raise RuntimeError("Tavily SDK not installed. Run: pip install tavily-python")
    
    if not settings.tavily_api_key:
        raise RuntimeError("TAVILY_API_KEY not configured")
    
    client = TavilyClient(api_key=settings.tavily_api_key)
    result = await asyncio.to_thread(
        client.search, 
        query=query, 
        max_results=max_results, 
        include_images=False
    )
    
    documents: List[MCPDocument] = []
    for idx, item in enumerate(result.get("results", [])):
        documents.append(
            MCPDocument(
                id=item.get("id", str(idx)),
                title=item.get("title", "Untitled"),
                url=item.get("url", ""),
                snippet=item.get("content", ""),
                score=item.get("score", 0.0),
            )
        )
    return documents


async def run_web_search_with_fallback(query: str) -> Optional[SearchResult]:
    """Run web search with fallback chain: MCP → LangChain Tavily → SDK.
    
    Priority order:
    1. MCP Tavily (if configured) - Remote MCP server integration
    2. LangChain Tavily - Official LangChain integration (recommended by Tavily)
    3. Tavily SDK - Direct Python SDK as last resort
    """
    
    all_documents: List[MCPDocument] = []
    sources_used: List[str] = []
    
    # 1) Try MCP Tavily first (if configured)
    mcp_url = settings.mcp_tavily_url or os.getenv("MCP_TAVILY_URL")
    if mcp_url:
        try:
            tavily_docs = await _invoke_mcp_tavily(query, max_results=5)
            if tavily_docs:
                all_documents.extend(tavily_docs[:5])
                sources_used.append("tavily-mcp")
                logger.info("web_search.mcp_completed", document_count=len(tavily_docs))
        except Exception as exc:
            logger.warning("web_search.mcp_failed", error=str(exc))
    
    # 2) Fallback to LangChain Tavily (preferred method)
    if len(all_documents) < 3:
        try:
            lc_docs = await _run_tavily_langchain(query, max_results=5)
            existing_urls = {doc.url for doc in all_documents if doc.url}
            
            added_count = 0
            for doc in lc_docs:
                if doc.url not in existing_urls:
                    all_documents.append(doc)
                    added_count += 1
                    if len(all_documents) >= 5:
                        break
            
            if added_count > 0:
                sources_used.append("tavily-langchain")
                logger.info("web_search.langchain_completed", 
                          document_count=added_count,
                          total_documents=len(all_documents))
        except Exception as lc_exc:
            logger.warning("web_search.langchain_failed", error=str(lc_exc))
    
    # 3) Last resort: Direct Tavily SDK
    if len(all_documents) < 3:
        try:
            tavily_sdk_docs = await _run_tavily_sdk(query, max_results=5)
            existing_urls = {doc.url for doc in all_documents if doc.url}
            
            added_count = 0
            for doc in tavily_sdk_docs:
                if doc.url not in existing_urls:
                    all_documents.append(doc)
                    added_count += 1
                    if len(all_documents) >= 5:
                        break
            
            if added_count > 0:
                sources_used.append("tavily-sdk")
                logger.info("web_search.sdk_completed", 
                          document_count=added_count,
                          total_documents=len(all_documents))
        except Exception as sdk_exc:
            logger.warning("web_search.sdk_failed", error=str(sdk_exc))
    
    if not all_documents:
        logger.error("web_search.all_sources_failed", query=query)
        return None
    
    web_documents = [
        WebDocument(
            id=doc.id,
            title=doc.title,
            url=doc.url,
            snippet=doc.snippet,
            score=doc.score,
        )
        for doc in all_documents[:5]
    ]
    
    source = "+".join(sources_used) if sources_used else "unknown"
    logger.info("web_search.completed", 
               source=source,
               total_documents=len(web_documents),
               query=query)
    
    return SearchResult(query=query, source=source, documents=web_documents)