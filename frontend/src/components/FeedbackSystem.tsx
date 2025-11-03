import React, { useState, useRef } from "react";
import { ThumbsUp, ThumbsDown, X, AlertCircle, HelpCircle, AlertTriangle, RefreshCw, Upload } from "lucide-react";
import { Button } from "./ui/button";
import { Textarea } from "./ui/textarea";
import { FeedbackPayload } from "../types";

interface FeedbackSystemProps {
  messageId: string;
  onSubmit: (messageId: string, feedback: FeedbackPayload) => Promise<void> | void;
}

type FeedbackStage = "initial" | "negative-reason" | "better-solution" | "complete";
type NegativeReason = "wrong-answer" | "unclear" | "missing-steps" | "wrong-method" | null;

export function FeedbackSystem({ messageId, onSubmit }: FeedbackSystemProps) {
  const [stage, setStage] = useState<FeedbackStage>("initial");
  const [rating, setRating] = useState<"positive" | "negative" | null>(null);
  const [negativeReason, setNegativeReason] = useState<NegativeReason>(null);
  const [hasBetterSolution, setHasBetterSolution] = useState<boolean | null>(null);
  const [solutionText, setSolutionText] = useState("");
  const [uploadedFile, setUploadedFile] = useState<File | null>(null);
  const [fileBase64, setFileBase64] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleInitialRating = (isPositive: boolean) => {
    setRating(isPositive ? "positive" : "negative");
    
    if (isPositive) {
      // Positive feedback - done immediately
      const payload: FeedbackPayload = {
        thumbs_up: true,
        user_has_better_solution: false,
      };
      Promise.resolve(onSubmit(messageId, payload)).finally(() => setStage("complete"));
    } else {
      // Negative feedback - ask for more details
      setStage("negative-reason");
    }
  };

  const handleNegativeReason = (reason: NegativeReason) => {
    setNegativeReason(reason);
  };

  const handleBetterSolutionChoice = (hasIt: boolean) => {
    setHasBetterSolution(hasIt);
    
    if (hasIt) {
      setStage("better-solution");
    } else {
      // Submit feedback without solution
      const payload: FeedbackPayload = {
        thumbs_up: false,
        primary_issue: negativeReason ?? undefined,
        user_has_better_solution: false,
      };
      Promise.resolve(onSubmit(messageId, payload)).finally(() => setStage("complete"));
    }
  };

  const handleSolutionSubmit = () => {
    const payload: FeedbackPayload = {
      thumbs_up: false,
      primary_issue: negativeReason ?? undefined,
      user_has_better_solution: true,
      better_solution_text: solutionText || undefined,
      better_solution_pdf_base64: uploadedFile?.type === "application/pdf" ? fileBase64 : undefined,
      better_solution_image_base64: uploadedFile && uploadedFile.type.startsWith("image/") ? fileBase64 : undefined,
    };

    Promise.resolve(onSubmit(messageId, payload)).finally(() => setStage("complete"));
  };

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setUploadedFile(file);
      const reader = new FileReader();
      reader.onloadend = () => {
        setFileBase64(reader.result as string);
      };
      reader.readAsDataURL(file);
    }
  };

  if (stage === "complete") {
    return (
      <div className="text-center py-2">
        <p className="text-sm text-green-300">✓ Thank you for your feedback!</p>
      </div>
    );
  }

  if (stage === "initial") {
    return (
      <div className="space-y-2">
        <p className="text-sm text-white/90">Was this helpful?</p>
        <div className="flex gap-3">
          <Button
            onClick={() => handleInitialRating(true)}
            variant="outline"
            size="sm"
            className="bg-white/[0.05] border-0 hover:bg-green-500/20 text-white/90 shadow-md"
          >
            <ThumbsUp className="w-4 h-4 mr-2" />
            Helpful
          </Button>
          <Button
            onClick={() => handleInitialRating(false)}
            variant="outline"
            size="sm"
            className="bg-white/[0.05] border-0 hover:bg-red-500/20 text-white/90 shadow-md"
          >
            <ThumbsDown className="w-4 h-4 mr-2" />
            Not helpful
          </Button>
        </div>
      </div>
    );
  }

  if (stage === "negative-reason") {
    return (
      <div className="space-y-3">
        <p className="text-sm text-white/90">What went wrong?</p>
        <div className="grid grid-cols-2 gap-2">
          <Button
            onClick={() => handleNegativeReason("wrong-answer")}
            variant="outline"
            size="sm"
            className={`justify-start bg-white/[0.05] border-0 hover:bg-white/[0.12] text-white/90 shadow-md ${
              negativeReason === "wrong-answer" ? "bg-white/[0.15]" : ""
            }`}
          >
            <X className="w-4 h-4 mr-2" />
            Wrong answer
          </Button>
          <Button
            onClick={() => handleNegativeReason("unclear")}
            variant="outline"
            size="sm"
            className={`justify-start bg-white/[0.05] border-0 hover:bg-white/[0.12] text-white/90 shadow-md ${
              negativeReason === "unclear" ? "bg-white/[0.15]" : ""
            }`}
          >
            <HelpCircle className="w-4 h-4 mr-2" />
            Unclear
          </Button>
          <Button
            onClick={() => handleNegativeReason("missing-steps")}
            variant="outline"
            size="sm"
            className={`justify-start bg-white/[0.05] border-0 hover:bg-white/[0.12] text-white/90 shadow-md ${
              negativeReason === "missing-steps" ? "bg-white/[0.15]" : ""
            }`}
          >
            <AlertTriangle className="w-4 h-4 mr-2" />
            Missing steps
          </Button>
          <Button
            onClick={() => handleNegativeReason("wrong-method")}
            variant="outline"
            size="sm"
            className={`justify-start bg-white/[0.05] border-0 hover:bg-white/[0.12] text-white/90 shadow-md ${
              negativeReason === "wrong-method" ? "bg-white/[0.15]" : ""
            }`}
          >
            <RefreshCw className="w-4 h-4 mr-2" />
            Wrong method
          </Button>
        </div>
        
        {negativeReason && (
          <div className="space-y-2 pt-2 border-t border-white/20">
            <p className="text-sm text-white/90">Do you have a better solution?</p>
            <div className="flex gap-3">
              <Button
                onClick={() => handleBetterSolutionChoice(true)}
                variant="outline"
                size="sm"
                className="bg-white/[0.05] border-0 hover:bg-white/[0.12] text-white/90 shadow-md"
              >
                Yes
              </Button>
              <Button
                onClick={() => handleBetterSolutionChoice(false)}
                variant="outline"
                size="sm"
                className="bg-white/[0.05] border-0 hover:bg-white/[0.12] text-white/90 shadow-md"
              >
                No
              </Button>
            </div>
          </div>
        )}
      </div>
    );
  }

  if (stage === "better-solution") {
    return (
      <div className="space-y-3">
        <p className="text-sm text-white/90">Share your solution:</p>
        
        <Textarea
          placeholder="Type your solution here..."
          value={solutionText}
          onChange={(e) => setSolutionText(e.target.value)}
          className="bg-white/[0.05] border-0 text-white/95 placeholder:text-white/40 min-h-[100px] backdrop-blur-sm focus:ring-0 shadow-md"
        />
        
        <div className="space-y-2">
          <p className="text-xs text-white/70">Or upload a file:</p>
          <div className="flex gap-2">
            <label className="flex-1">
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,image/*"
                onChange={handleFileUpload}
                className="hidden"
              />
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="w-full bg-white/[0.05] border-0 hover:bg-white/[0.12] text-white/90 shadow-md"
                onClick={() => fileInputRef.current?.click()}
              >
                <Upload className="w-4 h-4 mr-2" />
                {uploadedFile ? uploadedFile.name : "Upload PDF/Image"}
              </Button>
            </label>
          </div>
        </div>
        
        <Button
          onClick={handleSolutionSubmit}
          disabled={!solutionText && !uploadedFile}
          className="w-full bg-gradient-to-r from-yellow-400 to-yellow-500 hover:from-yellow-500 hover:to-yellow-600 text-white border-0 shadow-lg"
        >
          Submit Feedback
        </Button>
      </div>
    );
  }

  return null;
}
