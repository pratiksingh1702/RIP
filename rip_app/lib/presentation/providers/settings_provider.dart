import 'dart:developer';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../../core/constants.dart';

final serverUrlProvider = StateProvider<String>((ref) {
  return AppConstants.defaultServerUrl;
});

final apiKeyProvider = StateProvider<String?>((ref) {
  return null;
});

final themeModeProvider = StateProvider<ThemeMode>((ref) {
  return ThemeMode.system;
});

final settingsProvider = FutureProvider<void>((ref) async {
  log('[settingsProvider] Loading settings...', name: 'SettingsProvider');
  final prefs = await SharedPreferences.getInstance();
  final savedServerUrl = prefs.getString(AppConstants.sharedPrefsServerUrlKey);
  final savedApiKey = prefs.getString(AppConstants.sharedPrefsApiKeyKey);
  final savedThemeMode = prefs.getString(AppConstants.sharedPrefsThemeModeKey);
  log('[settingsProvider] Loaded serverUrl: $savedServerUrl, apiKey: ${savedApiKey != null ? "***" : "null"}, themeMode: $savedThemeMode', name: 'SettingsProvider');

  if (savedServerUrl != null) {
    ref.read(serverUrlProvider.notifier).state = savedServerUrl;
  }

  if (savedApiKey != null) {
    ref.read(apiKeyProvider.notifier).state = savedApiKey;
  }

  if (savedThemeMode != null) {
    switch (savedThemeMode) {
      case 'light':
        ref.read(themeModeProvider.notifier).state = ThemeMode.light;
        break;
      case 'dark':
        ref.read(themeModeProvider.notifier).state = ThemeMode.dark;
        break;
      default:
        ref.read(themeModeProvider.notifier).state = ThemeMode.system;
        break;
    }
  }
});

class SettingsNotifier extends Notifier<void> {
  @override
  void build() {}

  Future<void> saveServerUrl(String url) async {
    log('[SettingsNotifier] Saving serverUrl: $url', name: 'SettingsProvider');
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(AppConstants.sharedPrefsServerUrlKey, url);
    ref.read(serverUrlProvider.notifier).state = url;
    log('[SettingsNotifier] Saved serverUrl', name: 'SettingsProvider');
  }

  Future<void> saveApiKey(String? key) async {
    log('[SettingsNotifier] Saving apiKey: ${key != null ? "***" : "null"}', name: 'SettingsProvider');
    final prefs = await SharedPreferences.getInstance();
    if (key != null && key.isNotEmpty) {
      await prefs.setString(AppConstants.sharedPrefsApiKeyKey, key);
    } else {
      await prefs.remove(AppConstants.sharedPrefsApiKeyKey);
    }
    ref.read(apiKeyProvider.notifier).state = key;
    log('[SettingsNotifier] Saved apiKey', name: 'SettingsProvider');
  }

  Future<void> saveThemeMode(ThemeMode mode) async {
    log('[SettingsNotifier] Saving themeMode: $mode', name: 'SettingsProvider');
    final prefs = await SharedPreferences.getInstance();
    String modeStr;
    switch (mode) {
      case ThemeMode.light:
        modeStr = 'light';
        break;
      case ThemeMode.dark:
        modeStr = 'dark';
        break;
      case ThemeMode.system:
        modeStr = 'system';
        break;
    }
    await prefs.setString(AppConstants.sharedPrefsThemeModeKey, modeStr);
    ref.read(themeModeProvider.notifier).state = mode;
    log('[SettingsNotifier] Saved themeMode', name: 'SettingsProvider');
  }
}

final settingsNotifierProvider = NotifierProvider<SettingsNotifier, void>(SettingsNotifier.new);
