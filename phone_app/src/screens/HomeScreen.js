import { useFocusEffect } from '@react-navigation/native';
import React, { useCallback, useState } from 'react';
import { RefreshControl, ScrollView, Switch, Text, TouchableOpacity, View } from 'react-native';

import { api } from '../api';
import { useChat } from '../ChatStore';
import OneShotModal from '../OneShotModal';
import { colors, s } from '../theme';
import { GoalCheckinExtra } from './GoalsScreen';

export default function HomeScreen({ navigation }) {
  const [todo, setTodo] = useState(null);
  const [error, setError] = useState(null);
  const [narration, setNarration] = useState(null);
  const [oneShot, setOneShot] = useState(null); // {title, skill, params, renderExtra?}
  const { setTranscript } = useChat();

  const load = useCallback(() => {
    setError(null);
    api('GET', '/todo/today').then(setTodo).catch((e) => setError(e.message));
  }, []);
  useFocusEffect(load);

  const continueChat = (transcript) => {
    setTranscript(transcript);
    setOneShot(null);
    load();
    navigation.navigate('Chat');
  };

  const toggle = async (inst, value) => {
    await api('PATCH', `/task-instances/${inst.id}`, { status: value ? 'completed' : 'pending' });
    load();
  };

  const narrate = async () => {
    setNarration('thinking...');
    try {
      const r = await api('POST', '/skills/todo_narration/open', { params: {} });
      setNarration(r.message);
    } catch (e) {
      setNarration(e.message);
    }
  };

  if (error) {
    return (
      <ScrollView style={s.screen} refreshControl={<RefreshControl refreshing={false} onRefresh={load} />}>
        <View style={s.card}>
          <Text style={s.h2}>Can't reach the server</Text>
          <Text style={s.dim}>{error}</Text>
          <Text style={s.dim}>Check tailscale + the Settings tab, then pull to retry.</Text>
        </View>
      </ScrollView>
    );
  }
  if (!todo) return <View style={s.screen}><Text style={s.dim}>loading...</Text></View>;

  return (
    <ScrollView style={s.screen} refreshControl={<RefreshControl refreshing={false} onRefresh={load} />}>
      {todo.missed_yesterday.length > 0 && (
        <View style={[s.card, s.banner]}>
          <Text style={s.h2}>Missed yesterday</Text>
          <Text style={s.text}>{todo.missed_yesterday.map((m) => m.name).join(', ')}</Text>
          <TouchableOpacity
            style={[s.btn, { marginTop: 8 }]}
            onPress={() => setOneShot({ title: 'About yesterday...', skill: 'missed_yesterday', params: {} })}
          >
            <Text style={s.btnText}>Explain to the AI</Text>
          </TouchableOpacity>
        </View>
      )}

      {todo.goal_checkins_due.map((g) => (
        <View key={g.id} style={[s.card, s.banner]}>
          <Text style={s.h2}>Goal check-in due</Text>
          <Text style={s.text}>{g.goal}</Text>
          <TouchableOpacity
            style={[s.btn, { marginTop: 8 }]}
            onPress={async () => {
              const goals = await api('GET', '/goals');
              const goal = goals.find((x) => x.id === g.id);
              setOneShot({
                title: `Check-in: ${goal.goal}`,
                skill: 'goal_checkin',
                params: { goal_id: g.id },
                renderExtra: (extra, setExtra) => <GoalCheckinExtra goal={goal} extra={extra} setExtra={setExtra} />,
              });
            }}
          >
            <Text style={s.btnText}>Do the check-in</Text>
          </TouchableOpacity>
        </View>
      ))}

      <View style={s.card}>
        <Text style={s.h2}>Today — {todo.date}</Text>
        {todo.instances.length === 0 && <Text style={s.dim}>Nothing on the list. Add tasks in the Tasks tab.</Text>}
        {todo.instances.map((i) => (
          <View key={i.id} style={s.row}>
            <Switch
              value={i.status === 'completed'}
              onValueChange={(v) => toggle(i, v)}
              trackColor={{ true: colors.accent, false: colors.panel2 }}
            />
            <Text style={[s.text, s.grow, i.status === 'completed' && { color: colors.dim, textDecorationLine: 'line-through' }]}>
              {i.name}{i.time_of_day ? ` @ ${i.time_of_day}` : ''}
            </Text>
            <Text style={s.imp(i.importance)}>{i.importance}</Text>
          </View>
        ))}
        <TouchableOpacity style={[s.btn, { marginTop: 10 }]} onPress={narrate}>
          <Text style={s.btnText}>AI's take on today</Text>
        </TouchableOpacity>
        {narration && <View style={s.aiMsg}><Text style={s.text}>{narration}</Text></View>}
      </View>

      <View style={s.card}>
        <Text style={s.h2}>Due in the next 3 days</Text>
        {todo.upcoming.length === 0 && <Text style={s.dim}>Nothing coming up.</Text>}
        {todo.upcoming.map((u, idx) => (
          <View key={idx} style={s.row}>
            <Text style={[s.text, s.grow]}>{u.name}</Text>
            <Text style={s.dim}>{u.due}</Text>
          </View>
        ))}
      </View>

      <TouchableOpacity
        style={[s.btn, { marginBottom: 24 }]}
        onPress={() => setOneShot({ title: 'Mid-day check-in', skill: 'midday_checkin', params: {} })}
      >
        <Text style={s.btnText}>Mid-day check-in</Text>
      </TouchableOpacity>

      <OneShotModal
        visible={!!oneShot}
        {...(oneShot || { title: '', skill: 'midday_checkin' })}
        onClose={() => { setOneShot(null); load(); }}
        onContinueChat={continueChat}
      />
    </ScrollView>
  );
}
