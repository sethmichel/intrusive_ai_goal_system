import { useFocusEffect } from '@react-navigation/native';
import React, { useCallback, useState } from 'react';
import { Alert, ScrollView, Text, TextInput, TouchableOpacity, View } from 'react-native';

import { api } from '../api';
import { useChat } from '../ChatStore';
import OneShotModal from '../OneShotModal';
import { colors, s } from '../theme';

function Segmented({ options, value, onChange }) {
  return (
    <View style={{ flexDirection: 'row', gap: 6, marginBottom: 8 }}>
      {options.map((o) => (
        <TouchableOpacity
          key={o}
          style={[s.btn, { flex: 1 }, value === o && { borderColor: colors.accent }]}
          onPress={() => onChange(o)}
        >
          <Text style={[s.btnText, value === o && { color: colors.accent }]}>{o}</Text>
        </TouchableOpacity>
      ))}
    </View>
  );
}

export default function TasksScreen({ navigation }) {
  const [tasks, setTasks] = useState([]);
  const [error, setError] = useState(null);
  const [oneShot, setOneShot] = useState(null);
  const { setTranscript } = useChat();
  const [form, setForm] = useState({ task_type: 'recurring', name: '', importance: 'mid', frequency_days: '', due_date: '', time_of_day: '', reason: '' });

  const load = useCallback(() => {
    api('GET', '/tasks?include_deleted=true').then(setTasks).catch((e) => setError(e.message));
  }, []);
  useFocusEffect(load);

  const add = async () => {
    try {
      await api('POST', '/tasks', {
        task_type: form.task_type,
        name: form.name,
        importance: form.importance,
        frequency_days: form.task_type === 'recurring' ? parseInt(form.frequency_days, 10) || null : null,
        due_date: form.task_type === 'one_off' ? form.due_date || null : null,
        time_of_day: form.time_of_day || null,
        reason: form.reason || null,
      });
      setForm({ ...form, name: '', frequency_days: '', due_date: '', time_of_day: '', reason: '' });
      load();
    } catch (e) {
      Alert.alert('Could not add task', e.message);
    }
  };

  const restore = (t) => {
    // one-off restore asks for a new due date; no AI justification (per README)
    Alert.prompt
      ? Alert.prompt('New due date', 'YYYY-MM-DD', async (due) => {
          if (!due) return;
          try { await api('POST', `/tasks/${t.id}/restore`, { due_date: due }); load(); }
          catch (e) { Alert.alert('Restore failed', e.message); }
        })
      : null;
  };

  const active = tasks.filter((t) => !t.deleted_at);
  const deleted = tasks.filter((t) => t.deleted_at);

  return (
    <ScrollView style={s.screen}>
      {error && <View style={s.card}><Text style={{ color: colors.bad }}>{error}</Text></View>}

      <View style={s.card}>
        <Text style={s.h2}>Add a task</Text>
        <Text style={s.dim}>Day-to-day stuff. Long-term goals have their own tab.</Text>
        <TextInput style={[s.input, { marginTop: 8 }]} placeholder="Task name" placeholderTextColor={colors.dim}
          value={form.name} onChangeText={(v) => setForm({ ...form, name: v })} />
        <Segmented options={['recurring', 'one_off']} value={form.task_type} onChange={(v) => setForm({ ...form, task_type: v })} />
        <Segmented options={['low', 'mid', 'high']} value={form.importance} onChange={(v) => setForm({ ...form, importance: v })} />
        {form.task_type === 'recurring' ? (
          <TextInput style={s.input} placeholder="Every N days (e.g. 5)" placeholderTextColor={colors.dim}
            keyboardType="number-pad" value={form.frequency_days} onChangeText={(v) => setForm({ ...form, frequency_days: v })} />
        ) : (
          <TextInput style={s.input} placeholder="Due date YYYY-MM-DD" placeholderTextColor={colors.dim}
            value={form.due_date} onChangeText={(v) => setForm({ ...form, due_date: v })} />
        )}
        <TextInput style={s.input} placeholder="Reminder time HH:MM (optional)" placeholderTextColor={colors.dim}
          value={form.time_of_day} onChangeText={(v) => setForm({ ...form, time_of_day: v })} />
        <TextInput style={s.input} placeholder="Why this matters (optional -- the AI remembers it)" placeholderTextColor={colors.dim}
          value={form.reason} onChangeText={(v) => setForm({ ...form, reason: v })} />
        <TouchableOpacity style={[s.btn, s.btnPrimary]} onPress={add}>
          <Text style={s.btnPrimaryText}>Add</Text>
        </TouchableOpacity>
      </View>

      <View style={s.card}>
        <Text style={s.h2}>Your tasks</Text>
        {active.length === 0 && <Text style={s.dim}>No tasks yet.</Text>}
        {active.map((t) => (
          <View key={t.id} style={s.row}>
            <View style={s.grow}>
              <Text style={s.text}>{t.name}</Text>
              <Text style={s.dim}>
                {t.task_type === 'recurring' ? `every ${t.frequency_days}d` : `due ${t.due_date}`}
                {t.time_of_day ? ` @ ${t.time_of_day}` : ''}
              </Text>
            </View>
            <Text style={s.imp(t.importance)}>{t.importance}</Text>
            <TouchableOpacity
              style={s.btn}
              onPress={() => setOneShot({ title: `Deleting "${t.name}"`, skill: 'delete_task', params: { task_id: t.id } })}
            >
              <Text style={[s.btnText, { color: colors.bad }]}>Delete</Text>
            </TouchableOpacity>
          </View>
        ))}
      </View>

      {deleted.length > 0 && (
        <View style={[s.card, { marginBottom: 24 }]}>
          <Text style={s.h2}>Deleted history</Text>
          {deleted.map((t) => (
            <View key={t.id} style={s.row}>
              <View style={s.grow}>
                <Text style={[s.text, { color: colors.dim, textDecorationLine: 'line-through' }]}>{t.name}</Text>
                {!!t.deletion_reason && <Text style={s.dim}>"{t.deletion_reason}"</Text>}
              </View>
              {t.task_type === 'one_off' && (
                <TouchableOpacity style={s.btn} onPress={() => restore(t)}>
                  <Text style={s.btnText}>Restore</Text>
                </TouchableOpacity>
              )}
            </View>
          ))}
        </View>
      )}

      <OneShotModal
        visible={!!oneShot}
        {...(oneShot || { title: '', skill: 'delete_task' })}
        onClose={() => { setOneShot(null); load(); }}
        onContinueChat={(tr) => { setTranscript(tr); setOneShot(null); load(); navigation.navigate('Chat'); }}
      />
    </ScrollView>
  );
}
