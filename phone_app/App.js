import { NavigationContainer, DarkTheme } from '@react-navigation/native';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { StatusBar } from 'expo-status-bar';
import React from 'react';
import { Text } from 'react-native';

import { ChatProvider } from './src/ChatStore';
import { colors } from './src/theme';
import HomeScreen from './src/screens/HomeScreen';
import ChatScreen from './src/screens/ChatScreen';
import TasksScreen from './src/screens/TasksScreen';
import GoalsScreen from './src/screens/GoalsScreen';
import SettingsScreen from './src/screens/SettingsScreen';

const Tab = createBottomTabNavigator();

const ICONS = { Home: '☀', Chat: '✎', Tasks: '☑', Goals: '⚑', Settings: '⚙' };

const theme = {
  ...DarkTheme,
  colors: { ...DarkTheme.colors, background: colors.bg, card: colors.panel, primary: colors.accent, text: colors.text },
};

export default function App() {
  return (
    <ChatProvider>
      <NavigationContainer theme={theme}>
        <StatusBar style="light" />
        <Tab.Navigator
          screenOptions={({ route }) => ({
            headerStyle: { backgroundColor: colors.panel },
            headerTitleStyle: { color: colors.accent },
            tabBarStyle: { backgroundColor: colors.panel, borderTopColor: '#000' },
            tabBarActiveTintColor: colors.accent,
            tabBarInactiveTintColor: colors.dim,
            tabBarIcon: ({ color }) => <Text style={{ color, fontSize: 17 }}>{ICONS[route.name]}</Text>,
          })}
        >
          <Tab.Screen name="Home" component={HomeScreen} />
          <Tab.Screen name="Chat" component={ChatScreen} />
          <Tab.Screen name="Tasks" component={TasksScreen} />
          <Tab.Screen name="Goals" component={GoalsScreen} />
          <Tab.Screen name="Settings" component={SettingsScreen} />
        </Tab.Navigator>
      </NavigationContainer>
    </ChatProvider>
  );
}
