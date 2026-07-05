import { useFocusEffect } from '@react-navigation/native';
import React, { useCallback, useState } from 'react';
import { Alert, ScrollView, Switch, Text, TextInput, TouchableOpacity, View } from 'react-native';

import { api } from '../api';
import { useChat } from '../ChatStore';
import OneShotModal from '../OneShotModal';
import { colors, s } from '../theme';

// The structured part of a goal check-in (the free-text reply is the modal's
// own textarea): did you do each item, and optional replacements. Exported so
// HomeScreen's "check-in due" banner uses the identical control.
export function GoalCheckinExtra({ goal, extra, setExtra }) {
  return (
    <View>
      {[1, 2].map((n) => (
        <View key={n} style={s.row}>
          <Switch
            value={!!extra[`action_item_${n}_done`]}
            onValueChange={(v) => setExtra({ ...extra, [`action_item_${n}_done`]: v })}
            trackColor={{ true: colors.accent, false: colors.panel2 }}
          />
          <Text style={[s.dim, s.grow]}>I did item {n}: {goal[`action_item_${n}`] || '(not set)'}</Text>
        </View>
      ))}
      <TextInput style={[s.input, { marginTop: 8 }]} placeholder="Replace item 1 (blank = keep)" placeholderTextColor={colors.dim}
        value={extra.new_action_item_1 || ''} onChangeText={(v) => setExtra({ ...extra, new_action_item_1: v || null })} />
      <TextInput style={s.input} placeholder="Replace item 2 (blank = keep)" placeholderTextColor={colors.dim}
        value={extra.new_action_item_2 || ''} onChangeText={(v) => setExtra({ ...extra, new_action_item_2: v || null })} />
    </View>
  );
}

export default function GoalsScreen({ navigation }) {
  const [goals, setGoals] = useState([]);
  const [error, setError] = useState(null);
  const [oneShot, setOneShot] = useState(null);
  const [editing, setEditing] = useState(null); // {goal row, a1, a2}
  const { setTranscript } = useChat();
  const [form, setForm] = useState({ goal: '', blocking_reason: '', action_item_1: '', action_item_2: '' });

  const load = useCallback(() => {
    api('GET', '/goals').then(setGoals).catch((e) => setError(e.message));
  }, []);
  useFocusEffect(load);

  const add = async () => {
    try {
      await api('POST', '/goals', {
        goal: form.goal,
        blocking_reason: form.blocking_reason || null,
        action_item_1: form.action_item_1 || null,
        action_item_2: form.action_item_2 || null,
      });
      setForm({ goal: '', blocking_reason: '', action_item_1: '', action_item_2: '' });
      load();
    } catch (e) {
      Alert.alert('Could not add goal', e.message);
    }
  };

  const saveEdit = async () => {
    const g = editing.row;
    await api('PATCH', `/goals/${g.id}`, {
      goal: g.goal, blocking_reason: g.blocking_reason,
      action_item_1: editing.a1 || null, action_item_2: editing.a2 || null,
    });
    setEditing(null);
    load();
  };

  const checkin = (g) =>
    setOneShot({
      title: `Check-in: ${g.goal}`,
      skill: 'goal_checkin',
      params: { goal_id: g.id },
      renderExtra: (extra, setExtra) => <GoalCheckinExtra goal={g} extra={extra} setExtra={setExtra} />,
    });

  return (
    <ScrollView style={s.screen}>
      {error && <View style={s.card}><Text style={{ color: colors.bad }}>{error}</Text></View>}

      <View style={s.card}>
        <Text style={s.h2}>Add a long-term goal</Text>
        <TextInput style={s.input} placeholder="The goal (e.g. start going to the gym)" placeholderTextColor={colors.dim}
          value={form.goal} onChangeText={(v) => setForm({ ...form, goal: v })} />
        <TextInput style={s.input} placeholder="What's blocking it right now (optional)" placeholderTextColor={colors.dim}
          value={form.blocking_reason} onChangeText={(v) => setForm({ ...form, blocking_reason: v })} />
        <TextInput style={s.input} placeholder="Action item 1 (always exactly 2)" placeholderTextColor={colors.dim}
          value={form.action_item_1} onChangeText={(v) => setForm({ ...form, action_item_1: v })} />
        <TextInput style={s.input} placeholder="Action item 2" placeholderTextColor={colors.dim}
          value={form.action_item_2} onChangeText={(v) => setForm({ ...form, action_item_2: v })} />
        <TouchableOpacity style={[s.btn, s.btnPrimary]} onPress={add}>
          <Text style={s.btnPrimaryText}>Add</Text>
        </TouchableOpacity>
      </View>

      {goals.length === 0 && (
        <View style={s.card}><Text style={s.dim}>No goals yet. The AI will eventually ask why.</Text></View>
      )}

      {goals.map((g) => (
        <View key={g.id} style={s.card}>
          <Text style={s.h2}>{g.goal}</Text>
          {!!g.blocking_reason && <Text style={s.dim}>blocked by: {g.blocking_reason}</Text>}
          {editing?.row.id === g.id ? (
            <View>
              <TextInput style={[s.input, { marginTop: 8 }]} value={editing.a1} placeholder="Action item 1"
                placeholderTextColor={colors.dim} onChangeText={(v) => setEditing({ ...editing, a1: v })} />
              <TextInput style={s.input} value={editing.a2} placeholder="Action item 2"
                placeholderTextColor={colors.dim} onChangeText={(v) => setEditing({ ...editing, a2: v })} />
              <View style={{ flexDirection: 'row', gap: 8 }}>
                <TouchableOpacity style={[s.btn, s.grow]} onPress={() => setEditing(null)}><Text style={s.btnText}>Cancel</Text></TouchableOpacity>
                <TouchableOpacity style={[s.btn, s.btnPrimary, s.grow]} onPress={saveEdit}><Text style={s.btnPrimaryText}>Save</Text></TouchableOpacity>
              </View>
            </View>
          ) : (
            <View>
              <Text style={[s.text, { marginTop: 6 }]}>1. {g.action_item_1 || '(not set)'}</Text>
              <Text style={s.text}>2. {g.action_item_2 || '(not set)'}</Text>
              <Text style={[s.dim, { marginTop: 6 }]}>next check-in: {g.next_checkin_date}</Text>
              <View style={{ flexDirection: 'row', gap: 8, marginTop: 10 }}>
                <TouchableOpacity style={s.btn} onPress={() => setEditing({ row: g, a1: g.action_item_1 || '', a2: g.action_item_2 || '' })}>
                  <Text style={s.btnText}>Edit items</Text>
                </TouchableOpacity>
                <TouchableOpacity style={s.btn} onPress={() => checkin(g)}>
                  <Text style={s.btnText}>Check in</Text>
                </TouchableOpacity>
                <TouchableOpacity
                  style={s.btn}
                  onPress={() => setOneShot({ title: `Deleting goal "${g.goal}"`, skill: 'delete_goal', params: { goal_id: g.id } })}
                >
                  <Text style={[s.btnText, { color: colors.bad }]}>Delete</Text>
                </TouchableOpacity>
              </View>
            </View>
          )}
        </View>
      ))}

      <OneShotModal
        visible={!!oneShot}
        {...(oneShot || { title: '', skill: 'delete_goal' })}
        onClose={() => { setOneShot(null); load(); }}
        onContinueChat={(tr) => { setTranscript(tr); setOneShot(null); load(); navigation.navigate('Chat'); }}
      />
    </ScrollView>
  );
}
