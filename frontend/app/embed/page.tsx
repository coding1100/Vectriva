"use client";

import { useState, useEffect, useRef, useCallback, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { Send, Minimize2, MessageCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card } from "@/components/ui/card";
import { api } from "@/lib/api";

interface Message {
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
}

function EmbedWidgetContent() {
  const searchParams = useSearchParams();
  const apiKey = searchParams.get("key") || "";
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [primaryColor, setPrimaryColor] = useState("#3B82F6");
  const [welcomeMessage, setWelcomeMessage] = useState(
    "Hi! How can I help you today?"
  );
  const [customerTimezone, setCustomerTimezone] = useState("UTC");
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const streamingContentRef = useRef("");

  useEffect(() => {
    const detected =
      Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
    setCustomerTimezone(detected);
  }, []);

  useEffect(() => {
    const color = searchParams.get("color");
    const welcome = searchParams.get("welcome");
    if (color) setPrimaryColor(color);
    if (welcome) setWelcomeMessage(decodeURIComponent(welcome));
  }, [searchParams]);

  useEffect(() => {
    if (isOpen && messages.length === 0) {
      setMessages([
        {
          role: "assistant",
          content: welcomeMessage,
          timestamp: new Date(),
        },
      ]);
    }
  }, [isOpen, messages.length, welcomeMessage]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = useCallback(async () => {
    if (!input.trim() || !apiKey || isLoading) return;

    const userMessage: Message = {
      role: "user",
      content: input,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setIsLoading(true);
    streamingContentRef.current = "";

    const placeholderMsg: Message = {
      role: "assistant",
      content: "",
      timestamp: new Date(),
    };
    setMessages((prev) => [...prev, placeholderMsg]);

    try {
      await api.chatStreamWithKey(
        apiKey,
        input,
        {
          onStart: (convId) => {
            if (!conversationId) {
              setConversationId(convId);
            }
          },
          onToken: (token) => {
            streamingContentRef.current += token;
            const currentContent = streamingContentRef.current;
            setMessages((prev) => {
              const updated = [...prev];
              updated[updated.length - 1] = {
                ...updated[updated.length - 1],
                content: currentContent,
              };
              return updated;
            });
          },
          onDone: (_convId, _isEscalated) => {
            // Streaming complete
          },
          onError: (error) => {
            console.error("Stream error:", error);
            setMessages((prev) => {
              const updated = [...prev];
              updated[updated.length - 1] = {
                ...updated[updated.length - 1],
                content:
                  "Sorry, I encountered an error. Please try again.",
              };
              return updated;
            });
          },
        },
        conversationId || undefined,
        customerTimezone
      );
    } catch (err) {
      console.error("Stream failed:", err);
      setMessages((prev) => {
        const updated = [...prev];
        updated[updated.length - 1] = {
          ...updated[updated.length - 1],
          content: "Sorry, I encountered an error. Please try again.",
        };
        return updated;
      });
    } finally {
      setIsLoading(false);
    }
  }, [input, apiKey, isLoading, conversationId, customerTimezone]);

  if (!isOpen) {
    return (
      <div className="fixed bottom-4 right-4 z-50">
        <Button
          size="lg"
          className="h-14 w-14 rounded-full shadow-lg"
          style={{ backgroundColor: primaryColor }}
          onClick={() => setIsOpen(true)}
        >
          <MessageCircle className="h-6 w-6" />
        </Button>
      </div>
    );
  }

  return (
    <div className="fixed bottom-4 right-4 z-50">
      <Card className="flex h-[500px] w-[380px] flex-col shadow-2xl">
        <div
          className="flex items-center justify-between rounded-t-lg p-4 text-white"
          style={{ backgroundColor: primaryColor }}
        >
          <h3 className="font-semibold">Chat with us</h3>
          <div className="flex gap-2">
            <Button
              size="sm"
              variant="ghost"
              className="h-8 w-8 p-0 text-white hover:bg-white/20"
              onClick={() => setIsOpen(false)}
            >
              <Minimize2 className="h-4 w-4" />
            </Button>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          {messages.map((msg, idx) => (
            <div
              key={idx}
              className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
            >
              <div
                className={`max-w-[80%] rounded-lg px-4 py-2 ${
                  msg.role === "user"
                    ? "bg-primary text-primary-foreground"
                    : "bg-muted"
                }`}
                style={
                  msg.role === "user"
                    ? { backgroundColor: primaryColor, color: "white" }
                    : {}
                }
              >
                <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
                {msg.content && (
                  <p className="text-xs opacity-70 mt-1">
                    {msg.timestamp.toLocaleTimeString([], {
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </p>
                )}
              </div>
            </div>
          ))}
          {isLoading &&
            messages.length > 0 &&
            !messages[messages.length - 1].content && (
              <div className="flex justify-start">
                <div className="max-w-[80%] rounded-lg bg-muted px-4 py-2">
                  <div className="flex gap-1">
                    <div className="h-2 w-2 animate-bounce rounded-full bg-gray-400"></div>
                    <div
                      className="h-2 w-2 animate-bounce rounded-full bg-gray-400"
                      style={{ animationDelay: "0.1s" }}
                    ></div>
                    <div
                      className="h-2 w-2 animate-bounce rounded-full bg-gray-400"
                      style={{ animationDelay: "0.2s" }}
                    ></div>
                  </div>
                </div>
              </div>
            )}
          <div ref={messagesEndRef} />
        </div>

        <div className="border-t p-4">
          <div className="flex gap-2">
            <Input
              placeholder="Type your message..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  handleSend();
                }
              }}
              disabled={isLoading}
            />
            <Button
              size="icon"
              onClick={handleSend}
              disabled={isLoading || !input.trim()}
              style={{ backgroundColor: primaryColor }}
            >
              <Send className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </Card>
    </div>
  );
}

export default function EmbedWidget() {
  return (
    <Suspense
      fallback={
        <div className="fixed bottom-4 right-4 z-50">Loading...</div>
      }
    >
      <EmbedWidgetContent />
    </Suspense>
  );
}
