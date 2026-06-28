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
