import 'dart:developer';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../core/api/rip_client.dart';
import 'connection_provider.dart';

final llmConfigsProvider = FutureProvider<List<Map<String, dynamic>>>((ref) async {
  final client = ref.read(ripClientProvider);
  final response = await client.listLLMConfigs();
  final configs = (response['configs'] as List?)?.cast<Map<String, dynamic>>() ?? [];
  log('[LLMConfigProvider] Loaded ${configs.length} configs');
  return configs;
});

final preferredLLMConfigProvider = StateProvider<String?>((ref) => null);
