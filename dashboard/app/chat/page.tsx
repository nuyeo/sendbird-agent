"use client";

import { useEffect, useRef, useState } from "react";
import { AlertCircle, MessageCircle, Send } from "lucide-react";

const API_BASE = "http://localhost:8001";
const WS_BASE = "ws://localhost:8001";

interface ChatMessage {
  id: string;
  role: "user" | "ai";
  text: string;
}

export default function ChatPage() {
  const [userId, setUserId] = useState("");
  const [connected, setConnected] = useState(false);
  const [connecting, setConnecting] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [typing, setTyping] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, typing]);

  useEffect(() => {
    return () => {
      wsRef.current?.close();
    };
  }, []);

  const connect = async () => {
    const trimmed = userId.trim();
    if (!trimmed) return;
    setConnecting(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/auth/dev-token`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: trimmed }),
      });
      if (!res.ok) {
        throw new Error(`토큰 발급 실패 (${res.status})`);
      }
      const { access_token } = (await res.json()) as { access_token: string };

      const ws = new WebSocket(
        `${WS_BASE}/ws/${encodeURIComponent(trimmed)}?token=${encodeURIComponent(access_token)}`
      );
      ws.onopen = () => {
        setConnected(true);
        setConnecting(false);
      };
      ws.onmessage = (event) => {
        const data = JSON.parse(event.data) as { type: string; message?: string };
        if (data.type === "typing") {
          setTyping(true);
        } else if (data.type === "ai_response") {
          setTyping(false);
          setMessages((prev) => [
            ...prev,
            { id: crypto.randomUUID(), role: "ai", text: data.message ?? "" },
          ]);
        } else if (data.type === "error") {
          setError(data.message ?? "Unknown error");
          setTyping(false);
        }
      };
      ws.onclose = (event) => {
        setConnected(false);
        setTyping(false);
        if (event.code === 4001) setError("인증 실패");
        else if (event.code === 4002) setError("잘못된 메시지 형식");
      };
      ws.onerror = () => {
        setError("WebSocket 오류");
        setConnecting(false);
      };
      wsRef.current = ws;
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setConnecting(false);
    }
  };

  const send = () => {
    const text = input.trim();
    if (!text || !connected || !wsRef.current) return;
    wsRef.current.send(JSON.stringify({ type: "user_message", message: text }));
    setMessages((prev) => [
      ...prev,
      { id: crypto.randomUUID(), role: "user", text },
    ]);
    setInput("");
  };

  if (!connected) {
    return (
      <main className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 dark:from-gray-900 dark:to-gray-950 flex items-center justify-center p-4">
        <div className="bg-white dark:bg-gray-800 p-8 rounded-2xl shadow-lg border border-gray-100 dark:border-gray-700 w-full max-w-md space-y-6">
          <div className="text-center">
            <div className="w-12 h-12 mx-auto mb-4 bg-indigo-50 dark:bg-indigo-950 rounded-2xl flex items-center justify-center">
              <MessageCircle className="text-indigo-600 dark:text-indigo-400" size={24} />
            </div>
            <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">CS Chat</h1>
            <p className="text-gray-500 dark:text-gray-400 text-sm mt-1">user_id로 채팅을 시작하세요</p>
          </div>

          <div className="space-y-3">
            <input
              type="text"
              placeholder="user_id (예: alice)"
              value={userId}
              onChange={(e) => setUserId(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") connect();
              }}
              disabled={connecting}
              className="w-full px-4 py-3 border border-gray-200 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100 placeholder:text-gray-400 dark:placeholder:text-gray-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent disabled:bg-gray-50 dark:disabled:bg-gray-800"
            />
            <button
              onClick={connect}
              disabled={!userId.trim() || connecting}
              className="w-full px-4 py-3 bg-indigo-600 text-white rounded-lg font-medium hover:bg-indigo-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {connecting ? "연결 중..." : "채팅 시작"}
            </button>
          </div>

          {error && (
            <div className="flex items-start gap-2 p-3 bg-red-50 dark:bg-red-950 border border-red-100 dark:border-red-900 rounded-lg text-sm text-red-700 dark:text-red-300">
              <AlertCircle size={16} className="mt-0.5 flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 dark:from-gray-900 dark:to-gray-950 flex flex-col">
      <header className="bg-white dark:bg-gray-800 border-b border-gray-100 dark:border-gray-700 px-4 py-3 shadow-sm">
        <div className="max-w-3xl mx-auto flex items-center gap-3">
          <div className="w-8 h-8 bg-gradient-to-br from-indigo-400 to-purple-400 rounded-full flex items-center justify-center text-white text-xs font-bold">
            {userId.charAt(0).toUpperCase()}
          </div>
          <div>
            <p className="text-sm font-semibold text-gray-900 dark:text-gray-100">{userId}</p>
            <p className="text-xs text-green-600 dark:text-green-400 flex items-center gap-1">
              <span className="w-1.5 h-1.5 bg-green-500 rounded-full" />
              연결됨
            </p>
          </div>
        </div>
      </header>

      <div className="flex-1 overflow-y-auto px-4 py-6">
        <div className="max-w-3xl mx-auto space-y-4">
          {messages.length === 0 && (
            <div className="text-center text-gray-400 dark:text-gray-500 text-sm py-12">
              메시지를 입력하여 대화를 시작하세요
            </div>
          )}
          {messages.map((m) => (
            <div
              key={m.id}
              className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}
            >
              <div
                className={`max-w-[75%] px-4 py-2.5 rounded-2xl text-sm whitespace-pre-wrap break-words ${
                  m.role === "user"
                    ? "bg-indigo-600 text-white"
                    : "bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-100 border border-gray-100 dark:border-gray-700 shadow-sm"
                }`}
              >
                {m.text}
              </div>
            </div>
          ))}
          {typing && (
            <div className="flex justify-start">
              <div className="bg-white dark:bg-gray-800 border border-gray-100 dark:border-gray-700 shadow-sm px-4 py-3 rounded-2xl flex gap-1">
                <span
                  className="w-2 h-2 bg-gray-300 dark:bg-gray-500 rounded-full animate-bounce"
                  style={{ animationDelay: "0ms" }}
                />
                <span
                  className="w-2 h-2 bg-gray-300 dark:bg-gray-500 rounded-full animate-bounce"
                  style={{ animationDelay: "150ms" }}
                />
                <span
                  className="w-2 h-2 bg-gray-300 dark:bg-gray-500 rounded-full animate-bounce"
                  style={{ animationDelay: "300ms" }}
                />
              </div>
            </div>
          )}
          {error && (
            <div className="flex items-start gap-2 p-3 bg-red-50 dark:bg-red-950 border border-red-100 dark:border-red-900 rounded-lg text-sm text-red-700 dark:text-red-300">
              <AlertCircle size={16} className="mt-0.5 flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>
      </div>

      <footer className="bg-white dark:bg-gray-800 border-t border-gray-100 dark:border-gray-700 px-4 py-3">
        <div className="max-w-3xl mx-auto flex gap-2">
          <input
            type="text"
            placeholder="메시지를 입력하세요"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                send();
              }
            }}
            disabled={typing}
            className="flex-1 px-4 py-2.5 border border-gray-200 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100 placeholder:text-gray-400 dark:placeholder:text-gray-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent disabled:bg-gray-50 dark:disabled:bg-gray-800"
          />
          <button
            onClick={send}
            disabled={!input.trim() || typing}
            className="px-4 py-2.5 bg-indigo-600 text-white rounded-lg font-medium hover:bg-indigo-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
          >
            <Send size={16} />
            전송
          </button>
        </div>
      </footer>
    </main>
  );
}
