import { StyleSheet } from 'react-native';

export const colors = {
  bg: '#16161e',
  panel: '#1f1f2b',
  panel2: '#262636',
  text: '#e6e6f0',
  dim: '#9a9ab0',
  accent: '#89b4fa',
  good: '#a6e3a1',
  warn: '#f9e2af',
  bad: '#f38ba8',
};

export const s = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.bg, padding: 14 },
  card: { backgroundColor: colors.panel, borderRadius: 10, padding: 14, marginBottom: 12 },
  banner: { borderLeftWidth: 3, borderLeftColor: colors.warn },
  h2: { color: colors.accent, fontSize: 15, fontWeight: '600', marginBottom: 8 },
  text: { color: colors.text, fontSize: 14 },
  dim: { color: colors.dim, fontSize: 12.5 },
  row: {
    flexDirection: 'row', alignItems: 'center', gap: 8,
    paddingVertical: 8, borderBottomWidth: 1, borderBottomColor: '#2c2c3d',
  },
  grow: { flex: 1 },
  btn: {
    backgroundColor: colors.panel2, borderColor: '#3a3a4f', borderWidth: 1,
    borderRadius: 8, paddingVertical: 8, paddingHorizontal: 13, alignItems: 'center',
  },
  btnPrimary: { backgroundColor: colors.accent, borderWidth: 0 },
  btnText: { color: colors.text, fontSize: 13.5 },
  btnPrimaryText: { color: '#14141c', fontWeight: '600', fontSize: 13.5 },
  input: {
    backgroundColor: colors.panel2, color: colors.text, borderColor: '#3a3a4f',
    borderWidth: 1, borderRadius: 8, paddingVertical: 8, paddingHorizontal: 10,
    fontSize: 13.5, marginBottom: 8,
  },
  aiMsg: {
    backgroundColor: colors.panel2, borderLeftWidth: 3, borderLeftColor: colors.accent,
    borderRadius: 8, padding: 10, marginVertical: 6,
  },
  userMsg: { backgroundColor: '#2a3b55', borderRadius: 8, padding: 10, marginVertical: 6, marginLeft: 30 },
  imp: (level) => ({
    fontSize: 11, paddingVertical: 2, paddingHorizontal: 8, borderRadius: 99,
    overflow: 'hidden', backgroundColor: colors.panel2,
    color: level === 'high' ? colors.bad : level === 'mid' ? colors.warn : colors.dim,
  }),
});
