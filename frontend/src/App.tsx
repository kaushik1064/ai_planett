import React, { useState, useRef, useEffect } from "react";
import { AnomalousMatterHero } from "./components/GenerativeArtScene";
import { ChatMessage } from "./components/ChatMessage";
import { ChatInput } from "./components/ChatInput";
import { ChatSidebar } from "./components/ChatSidebar";
import { ScrollArea } from "./components/ui/scroll-area";
import { Message, OutgoingMessage, FeedbackPayload, AgentResponsePayload } from "./types";
import "katex/dist/katex.min.css";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

export default function App() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [isProcessing, setIsProcessing] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const hasMessages = messages.length > 0;

  useEffect(() => {
    // Auto-scroll to bottom when new messages arrive
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Initial load: Try to create a new session if none exists
  useEffect(() => {
    if (!sessionId) {
      startNewChat();
    } else {
      loadSessionHistory(sessionId);
    }
  }, [sessionId]);

  const startNewChat = async () => {
    try {
      const res = await fetch(`${API_BASE}/history/sessions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" }
      });
      const data = await res.json();
      setSessionId(data.id);
      setMessages([]);
    } catch (err) {
      console.error("Failed to create session", err);
    }
  };

  const loadSessionHistory = async (id: string) => {
    try {
      const res = await fetch(`${API_BASE}/history/sessions/${id}/messages`);
      if (res.ok) {
        const history: any[] = await res.json();
        // Convert DB messages to frontend Message format
        const uiMessages = history.map((msg: any) => ({
          id: msg.id,
          role: (msg.role === 'assistant' ? 'assistant' : 'user') as Message['role'],
          content: msg.content,
          // DB doesn't store all the metadata yet, so some fields might be missing for historical msgs
          agentResponse: msg.role === 'assistant' ? { answer: msg.content } : undefined
        }));
        setMessages(uiMessages as Message[]);
      }
    } catch (err) {
      console.error("Failed to load history", err);
    }
  };

  const sendToBackend = async (payload: OutgoingMessage, trace: { kbStatusId: string; webStatusId: string | null }) => {
    if (!sessionId) return;

    // 1. Save User Message to DB
    const userMsgReq = await fetch(`${API_BASE}/history/sessions/${sessionId}/messages?role=user&content=${encodeURIComponent(payload.text || "Shared an image/audio")}`, { method: "POST" });

    try {
      const response = await fetch(`${API_BASE}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query: payload.text ?? "",
          modality: payload.modality,
          image_base64: payload.imageBase64,
          audio_base64: payload.audioBase64,
        }),
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(errorText || "Request failed");
      }

      const data: AgentResponsePayload = await response.json();

      // 2. Save AI Response to DB
      await fetch(`${API_BASE}/history/sessions/${sessionId}/messages?role=assistant&content=${encodeURIComponent(data.answer)}`, { method: "POST" });

      setMessages((prev) => {
        const withoutStatus = prev.filter((msg) => msg.id !== trace.kbStatusId && msg.id !== trace.webStatusId);
        return [
          ...withoutStatus,
          {
            id: `assistant-${Date.now()}`,
            role: "assistant",
            content: data.answer,
            steps: data.steps,
            knowledgeHits: data.knowledge_hits,
            citations: data.citations,
            showFeedback: data.feedback_required,
            agentResponse: data,
            source: data.source,
            trace: data.gateway_trace,
            originalQuery: payload.text ?? "",
          },
        ];
      });
    } catch (error: any) {
      console.error(error);
      const errorId = `status-error-${Date.now()}`;
      setMessages((prev) => [
        ...prev.filter((msg) => msg.id !== trace.kbStatusId && msg.id !== trace.webStatusId),
        {
          id: errorId,
          role: "status",
          statusType: "error",
          content: typeof error?.message === "string" ? error.message : "Unable to process the request.",
        },
      ]);
    } finally {
      setIsProcessing(false);
    }
  };

  const handleSendMessage = (payload: OutgoingMessage) => {
    const baseContent = payload.text?.trim() || (payload.modality === "image" ? "Uploaded an image" : "Shared a voice note");
    const userMessage: Message = {
      id: `user-${Date.now()}`,
      role: "user",
      content: baseContent,
      modality: payload.modality,
      imagePreview: payload.imageBase64 ?? undefined,
    };

    const kbStatusId = `status-kb-${Date.now()}`;
    const trace = { kbStatusId, webStatusId: null as string | null };

    setMessages((prev) => [
      ...prev,
      userMessage,
      {
        id: kbStatusId,
        role: "status",
        statusType: "searching-kb",
        content: "Searching knowledge base...",
      },
    ]);

    setIsProcessing(true);

    const webStatusTimer = setTimeout(() => {
      trace.webStatusId = `status-web-${Date.now()}`;
      setMessages((prev) => [
        ...prev,
        {
          id: trace.webStatusId!,
          role: "status",
          statusType: "searching-web",
          content: "Checking web sources...",
        },
      ]);
    }, 1200);

    sendToBackend(payload, trace).finally(() => clearTimeout(webStatusTimer));
  };

  const handleFeedbackSubmit = async (messageId: string, feedback: FeedbackPayload) => {
    // ... (same as before)
  };

  return (
    <div className="relative w-full h-screen overflow-hidden flex">
      {/* Animated Background - Needs to be absolute to cover whole screen */}
      <div className="absolute inset-0 z-0">
        <AnomalousMatterHero />
      </div>

      {/* Sidebar - z-30 to be clickable */}
      <div className="relative z-30 flex-shrink-0 h-full">
        <ChatSidebar
          currentSessionId={sessionId}
          onSelectSession={setSessionId}
          onNewChat={startNewChat}
        />
      </div>

      {/* Chat Container - z-20 */}
      <div className="relative z-20 flex-1 flex flex-col h-full min-w-0">
        {/* Messages Area */}
        {hasMessages ? (
          <div className="flex-1 overflow-hidden flex items-end justify-center p-4 md:p-8 pb-4">
            <div className="w-full max-w-[48rem] h-full max-h-[calc(100vh-200px)] backdrop-blur-[100px] bg-white/[0.015] rounded-[2rem] shadow-[0_8px_40px_0_rgba(0,0,0,0.4),inset_0_0_80px_0_rgba(255,255,255,0.02)] overflow-hidden animate-in slide-in-from-bottom-4 duration-500">
              <ScrollArea className="h-full px-6 py-6">
                <div className="space-y-4">
                  {messages.map((message) => (
                    <ChatMessage
                      key={message.id}
                      message={message}
                      onFeedbackSubmit={handleFeedbackSubmit}
                    />
                  ))}
                </div>
                <div ref={messagesEndRef} />
              </ScrollArea>
            </div>
          </div>
        ) : (
          <div className="flex-1"></div>
        )}

        {/* Input Box */}
        <div className="flex items-end justify-center p-4 md:p-8 pt-0">
          <div className="w-full max-w-[48rem] backdrop-blur-[100px] bg-white/[0.015] rounded-[2rem] shadow-[0_8px_40px_0_rgba(0,0,0,0.4),inset_0_0_80px_0_rgba(255,255,255,0.02)] px-4 md:px-6 py-4">
            <ChatInput onSendMessage={handleSendMessage} disabled={isProcessing} />
          </div>
        </div>
      </div>
    </div>
  );
}
