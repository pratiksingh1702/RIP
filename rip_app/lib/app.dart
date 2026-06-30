import 'dart:developer';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'core/design/app_theme.dart';
import 'presentation/providers/settings_provider.dart';
import 'presentation/router/app_router.dart';

class App extends ConsumerWidget {
  const App({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    log('[App] Building app...', name: 'App');
    final themeMode = ref.watch(themeModeProvider);

    return MaterialApp.router(
      title: 'RIP',
      theme: AppTheme.ripLightTheme,
      darkTheme: AppTheme.ripDarkTheme,
      themeMode: themeMode,
      routerConfig: appRouter,
      debugShowCheckedModeBanner: false,
    );
  }
}
