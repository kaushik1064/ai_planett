import React, { useState, useRef, useEffect } from "react";
import { AnomalousMatterHero } from "./components/GenerativeArtScene";
import { ChatMessage } from "./components/ChatMessage";
import { ChatInput } from "./components/ChatInput";
import { ScrollArea } from "./components/ui/scroll-area";
import { Message, OutgoingMessage, FeedbackPayload, AgentResponsePayload } from "./types";
import "katex/dist/katex.min.css"; // Import styles for LaTeX math

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

export default function App() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isProcessing, setIsProcessing] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const hasMessages = messages.length > 0;

  useEffect(() => {
    // Auto-scroll to bottom when new messages arrive
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const sendToBackend = async (payload: OutgoingMessage, trace: { kbStatusId: string; webStatusId: string | null }) => {
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
    const targetMessage = messages.find((msg) => msg.id === messageId);
    if (!targetMessage || !targetMessage.agentResponse) return;

    try {
      await fetch(`${API_BASE}/api/feedback`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message_id: messageId,
          query: targetMessage.originalQuery ?? "",
          agent_response: targetMessage.agentResponse,
          feedback,
        }),
      });
    } catch (error) {
      console.error("Failed to submit feedback", error);
    }

    setMessages((prev) => prev.map((msg) => (msg.id === messageId ? { ...msg, showFeedback: false } : msg)));
  };

  return (
    <div className="relative w-full h-screen overflow-hidden">
      {/* Animated Background */}
      <AnomalousMatterHero />

      {/* Chat Container - ChatGPT Style */}
      <div className="relative z-20 flex flex-col h-full">
        {/* Expandable Chat Messages Area - Only shows when there are messages */}
        {hasMessages && (
          <div className="flex-1 overflow-hidden flex items-end justify-center p-4 md:p-8 pb-4">
            <div className="w-full max-w-[48rem] h-full max-h-[calc(100vh-200px)] backdrop-blur-[100px] bg-white/[0.015] rounded-[2rem] shadow-[0_8px_40px_0_rgba(0,0,0,0.4),inset_0_0_80px_0_rgba(255,255,255,0.02)] overflow-hidden animate-in slide-in-from-bottom-4 duration-500">
              {/* Messages Area */}
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
        )}

        {/* Empty State - spacer when no messages */}
        {!hasMessages && (
          <div className="flex-1"></div>
        )}

        {/* Input Box - Always at bottom */}
        <div className="flex items-end justify-center p-4 md:p-8 pt-0">
          <div className="w-full max-w-[48rem] backdrop-blur-[100px] bg-white/[0.015] rounded-[2rem] shadow-[0_8px_40px_0_rgba(0,0,0,0.4),inset_0_0_80px_0_rgba(255,255,255,0.02)] px-4 md:px-6 py-4">
            <ChatInput onSendMessage={handleSendMessage} disabled={isProcessing} />
          </div>
        </div>
      </div>
    </div>
  );
}
