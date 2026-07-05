import React, { useEffect, useState } from 'react';
import { Modal, ScrollView, Text, TextInput, TouchableOpacity, View } from 'react-native';
import { api } from './api';
import { colors, s } from './theme';

// The shared 1-shot AI conversation: AI opens -> user replies once -> AI
// closes, then the server writes the outcome (missed_reason, deletion_reason,
// goal_checkins row...). "Continue in chat" hands the in-memory transcript to
// the Chat tab; nothing is ever persisted (v1 design decision).
//
// props: visible, title, skill, params, renderExtra?(extraState, setExtraState),
//        initialExtra?, onClose(), onContinueChat(transcript)

export default function OneShotModal({
  visible, title, skill, params, renderExtra, initialExtra, onClose, onContinueChat,
}) {
  const [opening, setOpening] = useState(null);
  const [reply, setReply] = useState('');
  const [closing, setClosing] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [extra, setExtra] = useState(initialExtra || {});

  useEffect(() => {
    if (!visible) return;
    setOpening(null); setReply(''); setClosing(null); setError(null); setExtra(initialExtra || {});
    api('POST', `/skills/${skill}/open`, { params: params || {} })
      .then((r) => setOpening(r.message))
      .catch((e) => setError(e.message));
  }, [visible]);

  const send = async () => {
    if (!reply.trim() || busy) return;
    setBusy(true);
    try {
      const r = await api('POST', `/skills/${skill}/respond`, {
        params: params || {},
        transcript: [{ role: 'ai', text: opening }],
        user_message: reply.trim(),
        extra: renderExtra ? extra : null,
      });
      setClosing(r.message);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  const transcript = closing
    ? [{ role: 'ai', text: opening }, { role: 'user', text: reply.trim() }, { role: 'ai', text: closing }]
    : [];

  return (
    <Modal visible={visible} animationType="slide" transparent onRequestClose={onClose}>
      <View style={{ flex: 1, backgroundColor: 'rgba(0,0,0,0.6)', justifyContent: 'center', padding: 16 }}>
        <View style={[s.card, { maxHeight: '85%' }]}>
          <ScrollView>
            <Text style={s.h2}>{title}</Text>
            {error && <Text style={{ color: colors.bad }}>{error}</Text>}
            {!opening && !error && <Text style={s.dim}>thinking...</Text>}
            {opening && <View style={s.aiMsg}><Text style={s.text}>{opening}</Text></View>}

            {opening && !closing && (
              <>
                {renderExtra && renderExtra(extra, setExtra)}
                <TextInput
                  style={[s.input, { minHeight: 70 }]} multiline value={reply} onChangeText={setReply}
                  placeholder="Your answer..." placeholderTextColor={colors.dim}
                />
                <View style={{ flexDirection: 'row', gap: 8, justifyContent: 'flex-end' }}>
                  <TouchableOpacity style={s.btn} onPress={onClose}><Text style={s.btnText}>Cancel</Text></TouchableOpacity>
                  <TouchableOpacity style={[s.btn, s.btnPrimary]} onPress={send}>
                    <Text style={s.btnPrimaryText}>{busy ? '...' : 'Send'}</Text>
                  </TouchableOpacity>
                </View>
              </>
            )}

            {closing && (
              <>
                <View style={s.userMsg}><Text style={s.text}>{reply.trim()}</Text></View>
                <View style={s.aiMsg}><Text style={s.text}>{closing}</Text></View>
                <View style={{ flexDirection: 'row', gap: 8, justifyContent: 'flex-end' }}>
                  <TouchableOpacity style={s.btn} onPress={() => onContinueChat(transcript)}>
                    <Text style={s.btnText}>Continue in chat</Text>
                  </TouchableOpacity>
                  <TouchableOpacity style={[s.btn, s.btnPrimary]} onPress={onClose}>
                    <Text style={s.btnPrimaryText}>Done</Text>
                  </TouchableOpacity>
                </View>
              </>
            )}
          </ScrollView>
        </View>
      </View>
    </Modal>
  );
}
