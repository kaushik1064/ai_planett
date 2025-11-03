import React, { useState } from "react";
import { User, Bot, ChevronDown, ChevronUp } from "lucide-react";
import { FeedbackSystem } from "./FeedbackSystem";
import { Message, StatusType, FeedbackPayload } from "../types";

// Helper function to format mathematical content with better line breaks
function formatMathContent(text: string): React.ReactNode {
  if (!text) return null;
  
  // Split by double newlines to preserve paragraphs
  const paragraphs = text.split(/\n\n+/);
  
  return (
    <>
      {paragraphs.map((para, idx) => {
        const trimmedPara = para.trim();
        if (!trimmedPara) return null;
        
        const lines = trimmedPara.split('\n');
        const hasMultipleLines = lines.length > 1;
        
        // If single paragraph with no line breaks, render as simple text
        if (!hasMultipleLines && lines[0]) {
          return (
            <p key={idx} className={idx > 0 ? "mt-3" : ""}>
              {lines[0]}
            </p>
          );
        }
        
        // Multiple lines - format each line appropriately
        return (
          <div key={idx} className={idx > 0 ? "mt-3" : ""}>
            {lines.map((line, lineIdx) => {
              const trimmedLine = line.trim();
              if (!trimmedLine && lineIdx < lines.length - 1) {
                return <br key={lineIdx} />;
              }
              
              // Handle bullet points or numbered lists
              if (trimmedLine.match(/^[\-\*•]\s/) || trimmedLine.match(/^\d+[\.\)]\s/)) {
                return (
                  <div key={lineIdx} className="ml-4 mb-1.5 leading-relaxed">
                    {trimmedLine}
                  </div>
                );
              }
              
              // Regular lines
              return (
                <div key={lineIdx} className="mb-1.5 leading-relaxed last:mb-0">
                  {trimmedLine}
                </div>
              );
            })}
          </div>
        );
      })}
    </>
  );
}

// Extract a concise final answer from a possibly long answer string
function extractConciseAnswer(text?: string): string {
  if (!text) return "";
  const t = text.trim();
  // Prefer "Final Answer:" if present
  const finalMatch = t.match(/Final Answer\s*[:\-]\s*(.+)/i);
  if (finalMatch && finalMatch[1]) return finalMatch[1].trim();
  // Or "Answer:" format
  const ansMatch = t.match(/^(?:Answer\s*[:\-]\s*)(.+)$/im);
  if (ansMatch && ansMatch[1]) return ansMatch[1].trim();
  // Try to capture a last evaluated value like "= 10" or a concise last line
  const equalsMatch = t.match(/=\s*([^=\n]+)\s*$/m);
  if (equalsMatch && equalsMatch[1]) return equalsMatch[1].trim();
  const lastLine = t.split(/\n+/).map(s => s.trim()).filter(Boolean).pop();
  if (lastLine) return lastLine;
  // Otherwise, search lines for a concise result-like statement
  const lines = t.split(/\n+/).map(s => s.trim()).filter(Boolean);
  // Try the last equation/short numeric-ish line
  for (let i = lines.length - 1; i >= 0; i--) {
    const line = lines[i];
    const isShort = line.length <= 80;
    const looksLikeResult = /(=|≈|≃|→)\s*[-+]?\d+(?:[\/.]\d+)?(?:\s*[/·]\s*\d+)?\s*$/.test(line)
      || /^[-+]?\d+(?:[\/.]\d+)?(?:\s*[/·]\s*\d+)?\s*$/.test(line)
      || /\bunits?\b/i.test(line);
    if (isShort && looksLikeResult) return line;
  }
  // Fallback: pick the last short line available
  const lastShort = [...lines].reverse().find(l => l.length <= 80);
  if (lastShort) return lastShort;
  // Final fallback: trim long text
  return t.length > 120 ? t.slice(0, 120).trim() + "…" : t;
}

// Render step content as point-wise items (bulleted), avoiding bulky paragraphs
function renderStepPoints(text: string): React.ReactNode {
  if (!text) return null;
  // Remove any leading Answer/Final Answer lines from steps to avoid duplication
  const raw = text
    .split(/\n+/)
    .filter(l => !/^\s*(final\s+answer|answer)\s*[:\-]?/i.test(l))
    .join("\n")
    .trim();
  // Primary split by existing line breaks
  let parts = raw.split(/\n+/).map(s => s.trim()).filter(Boolean);
  // If it's a single bulky line, split by sentence-ish boundaries
  if (parts.length <= 1 && raw.length > 160) {
    parts = raw.split(/(?<=[\.\!\?])\s+(?=[A-Z0-9(])/).map(s => s.trim()).filter(Boolean);
  }
  // If nothing remains after filtering (e.g., input only had an Answer line),
  // fall back to original text lines so we still show an explanation.
  if (parts.length === 0) {
    parts = text.split(/\n+/).map(s => s.trim()).filter(Boolean);
  }
  return (
    <ul className="list-disc ml-6 space-y-1.5">
      {parts.map((p, i) => (
        <li key={i} className="leading-relaxed">{p}</li>
      ))}
    </ul>
  );
}

interface ChatMessageProps {
  message: Message;
  onFeedbackSubmit?: (messageId: string, feedback: FeedbackPayload) => void;
}

export function ChatMessage({ message, onFeedbackSubmit }: ChatMessageProps) {
  const [showSources, setShowSources] = useState(false);
  
  if (message.role === "status") {
    return (
      <div className="flex justify-center py-4">
        <div className="flex items-center gap-3 px-6 py-3 rounded-full bg-white/[0.08] backdrop-blur-xl shadow-[0_4px_20px_0_rgba(0,0,0,0.25)]">
          <div className="relative flex h-5 w-5">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-yellow-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-5 w-5 bg-gradient-to-r from-yellow-400 to-yellow-500"></span>
          </div>
          <span className="text-sm text-white/90">
            {message.statusType === "searching-kb" && "Searching in knowledge base..."}
            {message.statusType === "searching-web" && "Searching the web..."}
            {message.statusType === "processing" && "Processing your request..."}
            {message.statusType === "error" && message.content}
          </span>
        </div>
      </div>
    );
  }

  const isUser = message.role === "user";

  return (
    <div className={`flex gap-4 ${isUser ? "flex-row-reverse" : "flex-row"} mb-6`}>
      <div className={`flex-shrink-0 w-10 h-10 rounded-full flex items-center justify-center ${
        isUser ? "bg-gradient-to-br from-yellow-500 to-yellow-600 shadow-lg" : "bg-gradient-to-br from-yellow-400 to-yellow-500 shadow-lg"
      }`}>
        {isUser ? <User className="w-5 h-5 text-white" /> : <Bot className="w-5 h-5 text-white" />}
      </div>
      
      <div className={`flex-1 ${isUser ? "flex justify-end" : ""}`}>
        <div className={`inline-block max-w-[80%] ${
          isUser 
            ? "bg-white/[0.04] backdrop-blur-[100px]" 
            : "bg-white/[0.06] backdrop-blur-[100px]"
        } rounded-2xl px-5 py-3 shadow-[0_4px_28px_0_rgba(0,0,0,0.3),inset_0_0_40px_0_rgba(255,255,255,0.02)]`}>
          {message.imagePreview && (
            <img 
              src={message.imagePreview} 
              alt="User upload" 
              className="rounded-lg mb-3 max-w-full h-auto shadow-lg"
            />
          )}
          
          {/* Render explanation once: prefer steps; else show content even if Answer exists */}
          {!(message.steps && message.steps.length > 0) && (
            <div className="text-white/95">
              {renderStepPoints(message.content || "")}
            </div>
          )}
          
          {message.steps && message.steps.length > 0 && (
            <div className="mt-4 space-y-4">
              {message.steps.map((step, index) => (
                <div key={index} className="flex gap-3">
                  <div className="flex-shrink-0 w-6 h-6 rounded-full bg-yellow-500/40 backdrop-blur-sm shadow-md flex items-center justify-center">
                    <span className="text-xs text-white font-semibold">{index + 1}</span>
                  </div>
                  <div className="text-white/90 flex-1 min-w-0">
                    {step.title && (
                      <h4 className="font-semibold text-white/95 mb-2 text-base">{step.title}</h4>
                    )}
                    <div className="text-white/90 leading-relaxed break-words">
                      {renderStepPoints(step.content || step.explanation || "")}
                    </div>
                    {step.expression && (
                      <div className="mt-3 p-3 rounded-lg bg-white/[0.08] border border-white/10 overflow-x-auto">
                        <code className="text-yellow-300/90 text-sm font-mono break-all whitespace-pre-wrap block">
                          {step.expression}
                        </code>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Final Answer shown once, highlighted */}
          {message.agentResponse && message.agentResponse.answer && (
            <div className="mt-5 rounded-xl border border-yellow-400/40 bg-gradient-to-br from-yellow-500/10 to-transparent p-3">
              <div className="text-yellow-300 font-semibold mb-1 uppercase text-xs tracking-wide">Answer</div>
              <div className="text-white font-semibold text-lg">
                {extractConciseAnswer(message.agentResponse.answer)}
              </div>
            </div>
          )}

          {/* Collapsible Sources Section - Always show if there are KB results or citations */}
          {(message.knowledgeHits && message.knowledgeHits.length > 0) || 
           (message.citations && message.citations.length > 0) ? (
            <div className="mt-4 border-t border-white/10 pt-3">
              <button
                onClick={() => setShowSources(!showSources)}
                className="flex items-center gap-2 text-xs uppercase tracking-wide text-white/60 hover:text-white/80 transition-colors"
              >
                {showSources ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                Sources & Context {showSources ? "(Hide)" : "(Show)"}
              </button>
              
              {showSources && (
                <div className="mt-3 space-y-4">
                  {message.knowledgeHits && message.knowledgeHits.length > 0 && (
                    <div className="space-y-2">
                      <p className="text-xs uppercase tracking-wide text-white/50">Knowledge snippets</p>
                      {message.knowledgeHits.map((hit, index) => (
                        <div key={index} className="rounded-xl bg-white/[0.04] p-3 border border-white/5">
                          <p className="text-white/80 text-sm font-semibold break-words">{hit.question}</p>
                          <p className="text-white/70 text-sm mt-1 break-words leading-relaxed whitespace-pre-wrap">{hit.answer}</p>
                          <p className="text-white/40 text-xs mt-2">Similarity: {(hit.similarity * 100).toFixed(1)}%</p>
                        </div>
                      ))}
                    </div>
                  )}
                  
                  {message.citations && message.citations.length > 0 && (
                    <div className="space-y-2">
                      <p className="text-xs uppercase tracking-wide text-white/50">Citations</p>
                      <ul className="space-y-1 text-sm">
                        {message.citations.map((citation, index) => (
                          <li key={index}>
                            <a href={citation.url} target="_blank" rel="noopener noreferrer" className="text-yellow-300 hover:text-yellow-200">
                              [{index + 1}] {citation.title}
                            </a>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {message.source && message.source !== "kb" && (
                    <div className="text-xs text-white/60">
                      <span className="uppercase tracking-wide">Source:</span> {message.source}
                    </div>
                  )}

                  {message.trace && message.trace.length > 0 && (
                    <div className="text-[11px] text-white/40">
                      Gateway Trace: {message.trace.join(" → ")}
                    </div>
                  )}
                </div>
              )}
            </div>
          ) : null}
          
          {message.showFeedback && !isUser && onFeedbackSubmit && message.agentResponse && (
            <div className="mt-4 pt-4 border-t border-white/10">
              <FeedbackSystem 
                messageId={message.id}
                onSubmit={onFeedbackSubmit}
              />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
