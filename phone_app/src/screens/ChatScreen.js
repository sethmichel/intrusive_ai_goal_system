import React, { useRef, useState } from 'react';
import { KeyboardAvoidingView, Platform, ScrollView, Text, TextInput, TouchableOpacity, View } from 'react-native';

import { api } from '../api';
import { useChat } from '../ChatStore';
import { colors, s } from '../theme';

export default function ChatScreen() {
  const { transcript, setTranscript } = useChat();
  const [text, setText] = useState('');
  const [busy, setBusy] = useState(false);
  const scroller = useRef(null);

  const send = async () => {
    const msg = text.trim();
    if (!msg || busy) return;
    setText('');
    const next = [...transcript, { role: 'user', text: msg }];
    setTranscript(next);
    setBusy(true);
    try {
      const r = await api('POST', '/chat', { messages: next });
      setTranscript([...next, { role: 'ai', text: r.message }]);
    } catch (e) {
      setTranscript([...next, { role: 'ai', text: '[error: ' + e.message + ']' }]);
    } finally {
      setBusy(false);
    }
  };

  return (
    <KeyboardAvoidingView style={s.screen} behavior={Platform.OS === 'ios' ? 'padding' : undefined} keyboardVerticalOffset={90}>
      <ScrollView ref={scroller} onContentSizeChange={() => scroller.current?.scrollToEnd()} style={{ flex: 1 }}>
        <Text style={[s.dim, { marginBottom: 8 }]}>
          Nothing here is saved -- close the app and the conversation is gone.
        </Text>
        {transcript.map((m, i) => (
          <View key={i} style={m.role === 'ai' ? s.aiMsg : s.userMsg}>
            <Text style={s.text}>{m.text}</Text>
          </View>
        ))}
        {busy && <Text style={s.dim}>thinking...</Text>}
      </ScrollView>
      <View style={{ flexDirection: 'row', gap: 8, paddingVertical: 8 }}>
        <TextInput
          style={[s.input, { flex: 1, marginBottom: 0 }]} value={text} onChangeText={setText}
          placeholder="Say something..." placeholderTextColor={colors.dim} multiline
        />
        <TouchableOpacity style={[s.btn, s.btnPrimary]} onPress={send}>
          <Text style={s.btnPrimaryText}>Send</Text>
        </TouchableOpacity>
      </View>
    </KeyboardAvoidingView>
  );
}
