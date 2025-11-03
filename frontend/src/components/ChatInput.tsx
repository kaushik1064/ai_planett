import React, { useState, useRef } from "react";
import { Send, Image, Mic, MicOff } from "lucide-react";
import { Button } from "./ui/button";
import { Textarea } from "./ui/textarea";
import { OutgoingMessage } from "../types";

interface ChatInputProps {
  onSendMessage: (message: OutgoingMessage) => void;
  disabled?: boolean;
}

export function ChatInput({ onSendMessage, disabled }: ChatInputProps) {
  const [message, setMessage] = useState("");
  const [isRecording, setIsRecording] = useState(false);
  const [selectedImage, setSelectedImage] = useState<string | null>(null);
  const [audioBase64, setAudioBase64] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);

  const handleSend = () => {
    if (!message.trim() && !selectedImage && !audioBase64) {
      return;
    }

    if (selectedImage) {
      onSendMessage({
        text: message,
        modality: "image",
        imageBase64: selectedImage,
      });
    } else if (audioBase64) {
      onSendMessage({
        text: message,
        modality: "audio",
        audioBase64,
      });
    } else {
      onSendMessage({
        text: message,
        modality: "text",
      });
    }

      setMessage("");
      setSelectedImage(null);
    setAudioBase64(null);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleImageUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      const reader = new FileReader();
      reader.onloadend = () => {
        setSelectedImage(reader.result as string);
      };
      reader.readAsDataURL(file);
    }
  };

  const toggleVoiceInput = async () => {
    if (isRecording) {
      if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
        mediaRecorderRef.current.stop();
      }
      setIsRecording(false);
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mediaRecorder = new MediaRecorder(stream);
      audioChunksRef.current = [];

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      mediaRecorder.onstop = () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: "audio/webm" });
        const reader = new FileReader();
        reader.onloadend = () => {
          setAudioBase64(reader.result as string);
        };
        reader.readAsDataURL(audioBlob);
        setIsRecording(false);
        stream.getTracks().forEach((track) => track.stop());
      };

      mediaRecorderRef.current = mediaRecorder;
      mediaRecorder.start();
      setIsRecording(true);
    } catch (error) {
      console.error("Audio recording error", error);
      alert("Unable to access microphone. Please check permissions.");
    }
  };

  return (
    <div className="space-y-3">
      {selectedImage && (
        <div className="relative inline-block">
          <img 
            src={selectedImage} 
            alt="Selected" 
            className="max-h-32 rounded-lg shadow-lg"
          />
          <button
            onClick={() => setSelectedImage(null)}
            className="absolute -top-2 -right-2 w-6 h-6 rounded-full bg-red-500 hover:bg-red-600 text-white flex items-center justify-center shadow-lg"
          >
            ×
          </button>
        </div>
      )}
      
      <div className="flex gap-2">
        <div className="flex-1 relative">
          <Textarea
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask anything"
            disabled={disabled}
            className="bg-white/[0.04] border-0 text-white/95 placeholder:text-white/40 pr-24 resize-none min-h-[52px] max-h-[150px] backdrop-blur-sm focus:ring-0 shadow-none"
          />
          
          <div className="absolute right-2 bottom-2 flex gap-1">
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              onChange={handleImageUpload}
              className="hidden"
            />
            <Button
              type="button"
              size="sm"
              variant="ghost"
              onClick={() => fileInputRef.current?.click()}
              disabled={disabled}
              className="h-8 w-8 p-0 hover:bg-white/20 text-white/70 hover:text-white"
            >
              <Image className="w-4 h-4" />
            </Button>
            
            <Button
              type="button"
              size="sm"
              variant="ghost"
              onClick={toggleVoiceInput}
              disabled={disabled}
              className={`h-8 w-8 p-0 hover:bg-white/20 ${
                isRecording ? "text-red-400 hover:text-red-300" : "text-white/70 hover:text-white"
              }`}
            >
              {isRecording ? <MicOff className="w-4 h-4" /> : <Mic className="w-4 h-4" />}
            </Button>
          </div>
        </div>
        
        <Button
          onClick={handleSend}
          disabled={disabled || (!message.trim() && !selectedImage && !audioBase64)}
          className="bg-gradient-to-r from-yellow-400 to-yellow-500 hover:from-yellow-500 hover:to-yellow-600 text-white border-0 h-auto px-4 shadow-lg shadow-yellow-500/30"
        >
          <Send className="w-5 h-5" />
        </Button>
      </div>
      
      {(isRecording || audioBase64) && (
        <div className="flex items-center justify-between gap-2 text-sm text-white/90">
          <div className="flex items-center gap-2">
          <div className="relative flex h-3 w-3">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-3 w-3 bg-red-500"></span>
          </div>
            <span>{isRecording ? "Recording..." : "Voice note ready to send"}</span>
          </div>
          {!isRecording && audioBase64 && (
            <button
              onClick={() => setAudioBase64(null)}
              className="text-xs text-white/60 hover:text-white/90"
            >
              Clear
            </button>
          )}
        </div>
      )}
    </div>
  );
}
