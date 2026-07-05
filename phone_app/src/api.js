import AsyncStorage from '@react-native-async-storage/async-storage';

// Same REST contract as the computer dashboard -- the phone is just another
// client of the Pi. Server url + token are entered once on the Settings tab.

let cached = null;

export async function getClientConfig() {
  if (!cached) {
    const raw = await AsyncStorage.getItem('client_config');
    cached = raw ? JSON.parse(raw) : { server_url: '', api_token: '' };
  }
  return cached;
}

export async function setClientConfig(cfg) {
  cached = { ...cfg, server_url: (cfg.server_url || '').replace(/\/+$/, '') };
  await AsyncStorage.setItem('client_config', JSON.stringify(cached));
}

export async function api(method, path, body) {
  const cfg = await getClientConfig();
  if (!cfg.server_url) throw new Error('No server configured -- set it in Settings.');
  const resp = await fetch(cfg.server_url + path, {
    method,
    headers: {
      'Content-Type': 'application/json',
      Authorization: 'Bearer ' + cfg.api_token,
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!resp.ok) throw new Error(`${method} ${path} -> ${resp.status}: ${await resp.text()}`);
  return resp.json();
}
