import 'dart:developer';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'core/theme.dart';
import 'presentation/router/app_router.dart';
import 'presentation/providers/settings_provider.dart';

class App extends ConsumerWidget {
  const App({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    log('[App] Building app...', name: 'App');
    final themeMode = ref.watch(themeModeProvider);
    log('[App] Using themeMode: $themeMode', name: 'App');

    return MaterialApp.router(
      title: 'RIP',
      theme: AppTheme.lightTheme,
      darkTheme: AppTheme.darkTheme,
      themeMode: themeMode,
      routerConfig: appRouter,
      debugShowCheckedModeBanner: false,
    );
  }
}
