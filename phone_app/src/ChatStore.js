import React, { createContext, useContext, useState } from 'react';

// In-memory only: the chat transcript lives here so a 1-shot conversation can
// be "continued in chat" from any screen. Killing the app ends every
// conversation for good -- that's the intended v1 behavior.

const ChatContext = createContext(null);

export function ChatProvider({ children }) {
  const [transcript, setTranscript] = useState([]);
  return <ChatContext.Provider value={{ transcript, setTranscript }}>{children}</ChatContext.Provider>;
}

export function useChat() {
  return useContext(ChatContext);
}
