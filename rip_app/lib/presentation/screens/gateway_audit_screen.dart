// REPLACE the entire file:
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:rip_app/presentation/providers/connection_provider.dart';
import '../providers/gateway_provider.dart';

class GatewayAuditScreen extends ConsumerWidget {
  const GatewayAuditScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    // Use a simple FutureProvider instead of family
    final audit = ref.watch(_auditProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('Audit')),
      body: audit.when(
        data: (logs) {
          if (logs.isEmpty) {
            return const Center(child: Text('No audit entries yet.'));
          }
          return ListView.separated(
            padding: const EdgeInsets.all(16),
            itemCount: logs.length,
            separatorBuilder: (_, __) => const Divider(height: 1),
            itemBuilder: (context, index) {
              final log = logs[index] as Map;
              final allowed = log['allowed'] == true;
              return ListTile(
                dense: true,
                leading: Icon(
                  allowed ? Icons.verified_user_rounded : Icons.block_rounded,
                  color: allowed ? Colors.green : Colors.amber,
                ),
                title: Text('${log['action'] ?? 'Access decision'}'),
                subtitle: Text(
                  '${log['role'] ?? '-'} - ${log['source'] ?? 'all sources'}\n'
                  '${log['reason'] ?? log['session_id'] ?? ''}',
                ),
                isThreeLine: true,
              );
            },
          );
        },
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (error, _) => Center(child: Text('Audit unavailable: $error')),
      ),
    );
  }
}

// Simple provider without family params
final _auditProvider = FutureProvider<List<dynamic>>((ref) async {
  final client = ref.watch(ripClientProvider);
  try {
    return await client.gatewayAudit();
  } catch (e) {
    return [];
  }
});