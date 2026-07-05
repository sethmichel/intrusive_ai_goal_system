import React, { useEffect, useState } from 'react';
import { Alert, ScrollView, Text, TextInput, TouchableOpacity, View } from 'react-native';

import { api, getClientConfig, setClientConfig } from '../api';
import { colors, s } from '../theme';

export default function SettingsScreen() {
  const [cfg, setCfg] = useState({ server_url: '', api_token: '' });
  const [serverSettings, setServerSettings] = useState(null);
  const [status, setStatus] = useState('');

  useEffect(() => { getClientConfig().then(setCfg); }, []);

  const save = async () => {
    await setClientConfig(cfg);
    setStatus('checking...');
    try {
      await api('GET', '/health');
      setStatus('connected ✓');
      setServerSettings(await api('GET', '/settings'));
    } catch (e) {
      setStatus('cannot reach server: ' + e.message);
    }
  };

  const saveServer = async () => {
    try {
      const updated = await api('PUT', '/settings', {
        timezone: serverSettings.timezone,
        goal_checkin_interval_days: parseInt(serverSettings.goal_checkin_interval_days, 10),
      });
      setServerSettings(updated);
      Alert.alert('Saved');
    } catch (e) {
      Alert.alert('Save failed', e.message);
    }
  };

  return (
    <ScrollView style={s.screen}>
      <View style={s.card}>
        <Text style={s.h2}>Server connection</Text>
        <Text style={s.dim}>The Pi's tailscale address and the shared API token. Both devices must be on your tailnet.</Text>
        <TextInput style={[s.input, { marginTop: 8 }]} placeholder="http://100.x.y.z:8734" placeholderTextColor={colors.dim}
          autoCapitalize="none" autoCorrect={false} value={cfg.server_url}
          onChangeText={(v) => setCfg({ ...cfg, server_url: v })} />
        <TextInput style={s.input} placeholder="API token" placeholderTextColor={colors.dim}
          autoCapitalize="none" autoCorrect={false} secureTextEntry value={cfg.api_token}
          onChangeText={(v) => setCfg({ ...cfg, api_token: v })} />
        <TouchableOpacity style={[s.btn, s.btnPrimary]} onPress={save}>
          <Text style={s.btnPrimaryText}>Save & test</Text>
        </TouchableOpacity>
        {!!status && <Text style={[s.dim, { marginTop: 8 }]}>{status}</Text>}
      </View>

      {serverSettings && (
        <View style={s.card}>
          <Text style={s.h2}>Server settings</Text>
          <Text style={s.dim}>Timezone (IANA name -- defines when "today" rolls over)</Text>
          <TextInput style={s.input} value={serverSettings.timezone} autoCapitalize="none"
            onChangeText={(v) => setServerSettings({ ...serverSettings, timezone: v })} />
          <Text style={s.dim}>Goal check-in interval, days (7-21)</Text>
          <TextInput style={s.input} keyboardType="number-pad"
            value={String(serverSettings.goal_checkin_interval_days)}
            onChangeText={(v) => setServerSettings({ ...serverSettings, goal_checkin_interval_days: v })} />
          <TouchableOpacity style={[s.btn, s.btnPrimary]} onPress={saveServer}>
            <Text style={s.btnPrimaryText}>Save server settings</Text>
          </TouchableOpacity>
        </View>
      )}
    </ScrollView>
  );
}
