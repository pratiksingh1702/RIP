import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'connection_provider.dart';
import 'project_provider.dart';

// ── Gateway workflow providers ──

final gatewayWorkflowsProvider = FutureProvider<List<dynamic>>((ref) async {
  final client = ref.watch(ripClientProvider);
  final projectId = ref.watch(activeProjectIdProvider);
  return await client.gatewayWorkflows(projectId: projectId);
});

final gatewayPromptTemplatesProvider = FutureProvider<Map<String, dynamic>>((ref) async {
  final client = ref.watch(ripClientProvider);
  return await client.gatewayPromptTemplates();
});

final gatewayWorkflowPaletteProvider = FutureProvider<Map<String, dynamic>>((ref) async {
  final client = ref.watch(ripClientProvider);
  return await client.gatewayWorkflowPalette();
});

final gatewayLlmConfigsProvider = FutureProvider<List<Map<String, dynamic>>>((ref) async {
  final client = ref.watch(ripClientProvider);
  try {
    final result = await client.listLLMConfigs();
    final configs = result['configs'] as List? ?? [];
    return configs.map((c) => Map<String, dynamic>.from(c as Map)).toList();
  } catch (e) {
    return [];
  }
});

// ── Gateway role ──

final gatewayRoleProvider = StateProvider<String>((ref) => 'developer');

// ── Sources (for gateway_sources_screen) ──

final gatewaySourcesProvider = FutureProvider<Map<String, dynamic>>((ref) async {
  final client = ref.watch(ripClientProvider);
  try {
    return await client.gatewaySources();
  } catch (e) {
    return {'sources': []};
  }
});

// ── Metrics (for gateway_activity_screen) ──

final gatewayMetricsProvider = FutureProvider<Map<String, dynamic>>((ref) async {
  final client = ref.watch(ripClientProvider);
  try {
    return await client.gatewayMetrics();
  } catch (e) {
    return {};
  }
});

// ── Sessions (for gateway_activity_screen) ──

final gatewaySessionsProvider = FutureProvider<List<dynamic>>((ref) async {
  final client = ref.watch(ripClientProvider);
  try {
    return await client.gatewaySessions();
  } catch (e) {
    return [];
  }
});

// ── Audit (for gateway_audit_screen) ──

final gatewayAuditProvider = FutureProvider.autoDispose.family<List<dynamic>, Map<String, String?>>((ref, params) async {
  final client = ref.watch(ripClientProvider);
  try {
    return await client.gatewayAudit(
      sessionId: params['session_id'],
      role: params['role'],
    );
  } catch (e) {
    return [];
  }
});

// ── Connection summary (for mcp_export_screen) ──

final unifiedConnectionSummaryProvider = FutureProvider<Map<String, dynamic>>((ref) async {
  final client = ref.watch(ripClientProvider);
  try {
    return await client.gatewaySettings();
  } catch (e) {
    return {};
  }
});

