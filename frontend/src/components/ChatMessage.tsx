import React, { useState } from "react";
import { User, Bot, ChevronDown, ChevronUp } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import { FeedbackSystem } from "./FeedbackSystem";
import { Message, StatusType, FeedbackPayload } from "../types";

// Extract a concise final answer from a possibly long answer string
// Extract a concise final answer from a possibly long answer string
// Extract a concise final answer from a possibly long answer string
function extractConciseAnswer(text?: string): string {
  if (!text) return "";
  const t = text.trim();

  // 1. Explicit text markers (Robust to newlines and "So, the final answer is:")
  // Matches "Final Answer: ...", "The final answer is ...", etc.
  const explicitMatch = t.match(/(?:The\s+)?Final\s+Answer\s*(?:is)?\s*[:\-]\s*([\s\S]+)/i);
  if (explicitMatch && explicitMatch[1]) {
    let candidate = explicitMatch[1].trim();
    // Use only the first paragraph/line if it's too long
    const firstBlock = candidate.split(/\n\n/)[0].trim();
    // If the candidate contains LaTeX, return it nicely
    if (firstBlock.includes("$") || firstBlock.includes("\\")) {
      return firstBlock;
    }
    return firstBlock;
  }

  // 2. Look for \boxed{...} - highly specific to math answers
  const boxedMatch = t.match(/\\boxed{([\s\S]+?)}/);
  if (boxedMatch && boxedMatch[1]) {
    return `$$ ${boxedMatch[1]} $$`; // Wrap in display math
  }

  // 3. Look for the very last "math" block (single $ or double $$)
  // This captures the last equation in the text, which is usually the result.
  const latexMatches = [...t.matchAll(/(\$\$[\s\S]+?\$\$|\$[^\n]+?\$)/g)];
  if (latexMatches.length > 0) {
    return latexMatches[latexMatches.length - 1][0];
  }

  // 4. Fallback: Last line, if it looks significant
  const lines = t.split(/\n+/).map(s => s.trim()).filter(Boolean);
  const lastLine = lines.pop();
  if (lastLine && lastLine.length > 3) return lastLine;

  return "";
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
      <div className={`flex-shrink-0 w-10 h-10 rounded-full flex items-center justify-center ${isUser ? "bg-gradient-to-br from-yellow-500 to-yellow-600 shadow-lg" : "bg-gradient-to-br from-yellow-400 to-yellow-500 shadow-lg"
        }`}>
        {isUser ? <User className="w-5 h-5 text-white" /> : <Bot className="w-5 h-5 text-white" />}
      </div>

      <div className={`flex-1 ${isUser ? "flex justify-end" : ""}`}>
        <div className={`inline-block ${isUser
          ? "max-w-[80%] bg-white/[0.04] backdrop-blur-[100px]"
          : "w-full bg-white/[0.06] backdrop-blur-[100px]"
          } rounded-2xl px-5 py-3 shadow-[0_4px_28px_0_rgba(0,0,0,0.3),inset_0_0_40px_0_rgba(255,255,255,0.02)]`}>
          {message.imagePreview && (
            <img
              src={message.imagePreview}
              alt="User upload"
              className="rounded-lg mb-3 max-w-full h-auto shadow-lg"
            />
          )}

          {/* Main Content Rendered as Markdown + Math */}
          <div className={`prose prose-invert prose-p:leading-relaxed prose-pre:bg-black/50 prose-pre:p-0 max-w-none text-white/95 ${isUser ? "text-right" : "text-left"}`}>
            <ReactMarkdown
              remarkPlugins={[remarkMath]}
              rehypePlugins={[rehypeKatex]}
              components={{
                // Custom link style
                a: ({ node, ...props }) => <a {...props} className="text-yellow-300 hover:text-yellow-200 underline" target="_blank" rel="noopener" />,
                // Custom paragraphs with generous spacing and relaxed line height
                p: ({ node, ...props }) => <p className="mb-4 last:mb-0 leading-loose" {...props} />,
                // Custom headers for clear separation
                h1: ({ node, ...props }) => <h1 className="mt-8 mb-4 text-2xl font-bold text-yellow-500" {...props} />,
                h2: ({ node, ...props }) => <h2 className="mt-8 mb-4 text-xl font-bold text-yellow-400 border-b border-yellow-500/20 pb-2" {...props} />,
                h3: ({ node, ...props }) => <h3 className="mt-6 mb-3 text-lg font-semibold text-yellow-300" {...props} />,
                h4: ({ node, ...props }) => <h4 className="mt-6 mb-3 text-base font-semibold text-yellow-200" {...props} />,
                // Lists
                ul: ({ node, ...props }) => <ul className="my-4 pl-6 list-disc space-y-2" {...props} />,
                ol: ({ node, ...props }) => <ol className="my-4 pl-6 list-decimal space-y-2" {...props} />,
                li: ({ node, ...props }) => <li className="mb-1 leading-relaxed" {...props} />,
                // Blockquotes
                blockquote: ({ node, ...props }) => <blockquote className="border-l-4 border-yellow-500/50 pl-4 py-1 my-4 italic text-white/70" {...props} />,
                // Custom code block
                code: ({ node, className, children, ...props }) => {
                  const match = /language-(\w+)/.exec(className || '')
                  return match ? (
                    <div className="rounded-md bg-black/40 p-4 my-6 border border-white/10 overflow-x-auto shadow-inner">
                      <code className={className} {...props}>
                        {children}
                      </code>
                    </div>
                  ) : (
                    <code className="bg-white/10 rounded px-1.5 py-0.5 text-yellow-100 font-mono text-sm mx-1" {...props}>
                      {children}
                    </code>
                  )
                }
              }}
            >
              {message.content}
            </ReactMarkdown>
          </div>

          {/* Steps (If any, usually hidden by backend now, but good to support) */}
          {message.steps && message.steps.length > 0 && (
            <div className="mt-6 space-y-6 border-t border-white/10 pt-4">
              <div className="text-xs uppercase tracking-wide text-white/50 mb-2">Detailed Steps</div>
              {message.steps.map((step, index) => (
                <div key={index} className="flex gap-3">
                  <div className="flex-shrink-0 w-6 h-6 rounded-full bg-yellow-500/40 backdrop-blur-sm shadow-md flex items-center justify-center">
                    <span className="text-xs text-white font-semibold">{index + 1}</span>
                  </div>
                  <div className="text-white/90 flex-1 min-w-0">
                    {step.title && (
                      <h4 className="font-semibold text-white/95 mb-2 text-base">{step.title}</h4>
                    )}
                    <div className="prose prose-invert prose-sm max-w-none text-white/90">
                      <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>
                        {step.content || step.explanation || ""}
                      </ReactMarkdown>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Final Answer Highlight */}
          {message.agentResponse && message.agentResponse.answer && (
            <div className="mt-5 rounded-xl border border-yellow-400/40 bg-gradient-to-br from-yellow-500/10 to-transparent p-4 shadow-lg">
              <div className="text-yellow-300 font-semibold mb-2 uppercase text-xs tracking-wide">Final Result</div>
              <div className="text-white text-lg prose prose-invert max-w-none">
                <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>
                  {extractConciseAnswer(message.agentResponse.answer)}
                </ReactMarkdown>
              </div>
            </div>
          )}

          {/* Collapsible Sources Section */}
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
