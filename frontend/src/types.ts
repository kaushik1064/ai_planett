export type MessageRole = "user" | "assistant" | "status";

export type StatusType = "searching-kb" | "searching-web" | "processing" | "error";

export interface AgentStep {
  title: string;
  content: string;
  expression?: string;
  // Backward compatibility
  explanation?: string;
}

export interface AgentCitation {
  title: string;
  url: string;
}

export interface KnowledgeHit {
  document_id: string;
  question: string;
  answer: string;
  similarity: number;
}

export interface AgentResponsePayload {
  answer: string;
  steps: AgentStep[];
  retrieved_from_kb: boolean;
  knowledge_hits: KnowledgeHit[];
  citations: AgentCitation[];
  source: string;
  feedback_required: boolean;
  gateway_trace: string[];
}

export interface Message {
  id: string;
  role: MessageRole;
  content: string;
  statusType?: StatusType;
  steps?: AgentStep[];
  citations?: AgentCitation[];
  knowledgeHits?: KnowledgeHit[];
  showFeedback?: boolean;
  agentResponse?: AgentResponsePayload;
  source?: string;
  trace?: string[];
  error?: string;
  modality?: "text" | "image" | "audio";
  imagePreview?: string;
  originalQuery?: string;
}

export interface FeedbackPayload {
  thumbs_up: boolean;
  primary_issue?: "wrong-answer" | "unclear" | "missing-steps" | "wrong-method";
  user_has_better_solution: boolean;
  better_solution_text?: string;
  better_solution_pdf_base64?: string | null;
  better_solution_image_base64?: string | null;
}

export interface OutgoingMessage {
  text?: string;
  modality: "text" | "image" | "audio";
  imageBase64?: string;
  audioBase64?: string;
}

