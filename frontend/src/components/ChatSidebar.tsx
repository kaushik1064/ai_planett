import React, { useEffect, useState } from "react";
import { MessageSquare, Plus, Trash2, Menu, X } from "lucide-react";
import { Sheet, SheetContent, SheetTrigger } from "./ui/sheet";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

interface Session {
    id: string;
    title: string;
    created_at: string;
}

interface ChatSidebarProps {
    currentSessionId: string | null;
    onSelectSession: (id: string) => void;
    onNewChat: () => void;
}

// Export individual parts for flexible composition
export function ChatSidebar({ currentSessionId, onSelectSession, onNewChat }: ChatSidebarProps) {
    const [sessions, setSessions] = useState<Session[]>([]);

    // Mobile State
    const [isOpen, setIsOpen] = useState(false);

    useEffect(() => {
        fetchSessions();
    }, [currentSessionId]);

    const fetchSessions = async () => {
        try {
            const res = await fetch(`${API_BASE}/history/sessions`);
            if (res.ok) {
                const data = await res.json();
                setSessions(data);
            }
        } catch (err) {
            console.error("Failed to fetch sessions", err);
        }
    };

    const handleDelete = async (e: React.MouseEvent, id: string) => {
        e.stopPropagation();
        if (!confirm("Delete this chat?")) return;
        try {
            await fetch(`${API_BASE}/history/sessions/${id}`, { method: "DELETE" });
            setSessions(prev => prev.filter(s => s.id !== id));
            if (currentSessionId === id) onNewChat();
        } catch (err) {
            console.error("Failed to delete", err);
        }
    };

    const content = (
        <div className="flex flex-col h-full bg-black/40 border-r border-white/10 w-64 backdrop-blur-xl">
            <div className="p-4">
                <button
                    onClick={() => {
                        onNewChat();
                        setIsOpen(false);
                    }}
                    className="w-full flex items-center gap-2 bg-yellow-500 hover:bg-yellow-400 text-black font-semibold py-3 px-4 rounded-xl transition-all shadow-lg shadow-yellow-500/20"
                >
                    <Plus className="w-5 h-5" />
                    <span>New Chat</span>
                </button>
            </div>

            <div className="flex-1 overflow-y-auto px-2 space-y-1">
                {sessions.map((session) => (
                    <div
                        key={session.id}
                        onClick={() => {
                            onSelectSession(session.id);
                            setIsOpen(false);
                        }}
                        className={`group flex items-center justify-between p-3 rounded-lg cursor-pointer transition-all ${currentSessionId === session.id
                            ? "bg-white/10 text-yellow-300 shadow-inner"
                            : "text-white/60 hover:bg-white/5 hover:text-white"
                            }`}
                    >
                        <div className="flex items-center gap-3 overflow-hidden">
                            <MessageSquare className={`w-4 h-4 flex-shrink-0 ${currentSessionId === session.id ? "text-yellow-400" : "text-white/40"}`} />
                            <span className="truncate text-sm font-medium">{session.title}</span>
                        </div>
                        <button
                            onClick={(e) => handleDelete(e, session.id)}
                            className="opacity-0 group-hover:opacity-100 p-1 hover:bg-red-500/20 hover:text-red-400 rounded transition-all"
                        >
                            <Trash2 className="w-3.5 h-3.5" />
                        </button>
                    </div>
                ))}
                {sessions.length === 0 && (
                    <div className="text-center text-white/30 text-xs py-10">No history yet</div>
                )}
            </div>
            <div className="p-4 text-xs text-white/20 text-center border-t border-white/5">
                AI Math Mentor v1.0
            </div>
        </div>
    );

    return (
        <>
            {/* Desktop View */}
            <div className="hidden md:block h-full">
                {content}
            </div>

            {/* Mobile Toggle & Sheet */}
            <div className="md:hidden">
                {/* High Z-Index Button, Explicit OnClick */}
                <button
                    onClick={() => setIsOpen(true)}
                    className="fixed top-4 left-4 z-[100] p-2 bg-black/50 backdrop-blur-md border border-white/10 rounded-lg text-white shadow-lg hover:bg-white/10 transition-colors cursor-pointer"
                >
                    <Menu className="w-6 h-6" />
                </button>

                <Sheet open={isOpen} onOpenChange={setIsOpen}>
                    {/* No Trigger, state controlled manually */}
                    <SheetContent side="left" className="p-0 border-r border-white/10 bg-black w-64 text-white z-[110]">
                        {content}
                    </SheetContent>
                </Sheet>
            </div>
        </>
    );
}
