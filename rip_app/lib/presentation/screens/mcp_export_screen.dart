// REPLACE the entire file:
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../providers/gateway_provider.dart';

class McpExportScreen extends ConsumerWidget {
  const McpExportScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final settingsAsync = ref.watch(unifiedConnectionSummaryProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('MCP Export')),
      body: settingsAsync.when(
        data: (settings) {
          final config = const JsonEncoder.withIndent('  ').convert({
            'mcpServers': {
              'context-gateway': {
                'command': 'gateway',
                'args': ['mcp'],
                'env': {
                  'RIP_SERVER_URL': settings['server_url'] ?? '',
                  if ((settings['api_key'] ?? '').toString().isNotEmpty)
                    'RIP_API_KEYS': settings['api_key'],
                },
              },
            },
          });

          return ListView(
            padding: const EdgeInsets.all(16),
            children: [
              SelectableText(
                config,
                style: const TextStyle(fontFamily: 'monospace', fontSize: 13),
              ),
              const SizedBox(height: 12),
              FilledButton.icon(
                onPressed: () {
                  Clipboard.setData(ClipboardData(text: config));
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(content: Text('MCP config copied')),
                  );
                },
                icon: const Icon(Icons.copy_rounded),
                label: const Text('Copy JSON'),
              ),
            ],
          );
        },
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (err, _) => Center(child: Text('Settings unavailable: $err')),
      ),
    );
  }
}