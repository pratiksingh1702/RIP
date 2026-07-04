import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'connection_provider.dart';
import 'project_provider.dart';
import 'settings_provider.dart';

final gatewayRoleProvider = StateProvider<String>((ref) => 'developer');

final gatewayMetricsProvider = FutureProvider.autoDispose<Map<String, dynamic>>((ref) {
  return ref.watch(ripClientProvider).gatewayMetrics();
});

final gatewaySourcesProvider = FutureProvider.autoDispose<Map<String, dynamic>>((ref) {
  final projectId = ref.watch(activeProjectIdProvider);
  return ref.watch(ripClientProvider).gatewaySources(projectId: projectId);
});

final gatewaySourcePresetsProvider = FutureProvider.autoDispose<Map<String, dynamic>>((ref) {
  return ref.watch(ripClientProvider).gatewaySourcePresets();
});

final gatewaySettingsProvider = FutureProvider.autoDispose<Map<String, dynamic>>((ref) {
  return ref.watch(ripClientProvider).gatewaySettings();
});

final gatewaySessionsProvider = FutureProvider.autoDispose<List<dynamic>>((ref) {
  return ref.watch(ripClientProvider).gatewaySessions();
});

final gatewayAuditProvider = FutureProvider.autoDispose<List<dynamic>>((ref) {
  final role = ref.watch(gatewayRoleProvider);
  return ref.watch(ripClientProvider).gatewayAudit(role: role);
});

final unifiedConnectionSummaryProvider = Provider<Map<String, String?>>((ref) {
  return {
    'serverUrl': ref.watch(serverUrlProvider),
    'apiKey': ref.watch(apiKeyProvider),
    'role': ref.watch(gatewayRoleProvider),
  };
});
