# phone_app (iOS via Expo)

React Native app built with Expo so it can be written entirely on Windows and
compiled/signed on Expo's macOS build farm (the workaround chosen in
v1_design.md — no Mac, no paid developer account).

Tabs: **Home** (todo, missed-yesterday conversation, goal check-ins), **Chat**,
**Tasks**, **Goals**, **Settings** (server url + API token, stored on-device).

## develop (instant, no build needed)

```
cd phone_app
npm install
npx expo install --fix     # aligns native package versions with the Expo SDK
npx expo start
```

Scan the QR code with the **Expo Go** app on your iPhone (App Store, free).
Both devices need to reach the Pi — easiest is having the phone on the
tailnet too, then enter the Pi's tailscale URL + token in Settings.

## install on the phone for real (the weekly-resign route)

1. Make a free account at https://expo.dev, then `npm i -g eas-cli && eas login`.
2. `eas build --platform ios --profile preview` — EAS compiles and signs on
   their macOS farm. First run walks you through registering your Apple ID
   ("personal team", free) and your iPhone's UDID.
3. Download the resulting `.ipa`.
4. Install with **Sideloadly** (Windows app): iPhone over USB, point it at the
   `.ipa`, sign in with the same free Apple ID.
5. Free-account signatures expire every 7 days — reconnect USB and re-sideload
   weekly, or set up **AltStore/SideStore** to auto-refresh over wifi.
   $99/year Apple Developer removes the expiry entirely.

## notes

- No push notifications in v1 (needs Apple push infra); task-time reminders
  only exist as Windows toasts from the tray app. On the roadmap.
- Conversations are never saved: "Continue in chat" carries a 1-shot
  conversation to the Chat tab in memory only; killing the app ends it.
