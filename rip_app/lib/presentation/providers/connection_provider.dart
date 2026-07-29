import 'dart:developer';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../core/api/rip_client.dart';
import 'settings_provider.dart';

final ripClientProvider = Provider<RipClient>((ref) {
  final serverUrl = ref.watch(serverUrlProvider);
  final apiKey = ref.watch(apiKeyProvider);
  log('[connection_provider] Creating RipClient with serverUrl: $serverUrl', name: 'ConnectionProvider');
  return RipClient(serverUrl: serverUrl, apiKey: apiKey);
});

final connectionStatusProvider = FutureProvider.autoDispose<bool>((ref) async {
  log('[connection_provider] Checking connection status...', name: 'ConnectionProvider');
  final client = ref.watch(ripClientProvider);
  final result = await client.healthCheck();
  log('[connection_provider] Connection status: $result', name: 'ConnectionProvider');
  return result;
});

final isAuthenticatedProvider = FutureProvider.autoDispose<bool>((ref) async {
  final apiKey = ref.watch(apiKeyProvider);
  if (apiKey == null || apiKey.trim().isEmpty) {
    log('[connection_provider] No API key/session found -> Unauthenticated', name: 'ConnectionProvider');
    return false;
  }
  try {
    final client = ref.watch(ripClientProvider);
    final isHealthy = await client.healthCheck();
    if (!isHealthy) return false;
    await client.getCurrentUser();
    return true;
  } catch (e) {
    log('[connection_provider] Auth check failed: $e', name: 'ConnectionProvider');
    return false;
  }
});
