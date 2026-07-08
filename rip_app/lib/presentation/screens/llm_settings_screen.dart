import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:rip_app/presentation/providers/connection_provider.dart';
import '../providers/gateway_provider.dart';

class LlmSettingsScreen extends ConsumerStatefulWidget {
  const LlmSettingsScreen({super.key});

  @override
  ConsumerState<LlmSettingsScreen> createState() => _LlmSettingsScreenState();
}

class _LlmSettingsScreenState extends ConsumerState<LlmSettingsScreen> {
  @override
  Widget build(BuildContext context) {
    final configsAsync = ref.watch(gatewayLlmConfigsProvider);
    final cs = Theme.of(context).colorScheme;

    return Scaffold(
      appBar: AppBar(
        title: const Text('LLM Configurations'),
        actions: [
          IconButton(
            icon: const Icon(Icons.add_rounded),
            tooltip: 'Add model',
            onPressed: () => _showEditSheet(context, null, ref),
          ),
        ],
      ),
      body: configsAsync.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => Center(child: Text('Failed: $e')),
        data: (configs) {
          if (configs.isEmpty) {
            return Center(
              child: Column(mainAxisSize: MainAxisSize.min, children: [
                Icon(Icons.psychology_rounded, size: 64, color: cs.outline),
                const SizedBox(height: 16),
                Text('No LLM configs', style: Theme.of(context).textTheme.titleMedium),
                const SizedBox(height: 8),
                Text('Models from config.toml appear here.\nAdd custom ones with the + button.',
                    textAlign: TextAlign.center, style: Theme.of(context).textTheme.bodySmall),
              ]),
            );
          }
          return ListView.separated(
            padding: const EdgeInsets.all(16),
            itemCount: configs.length,
            separatorBuilder: (_, __) => const SizedBox(height: 8),
            itemBuilder: (context, index) {
              final cfg = configs[index];
              final id = cfg['id']?.toString() ?? '';
              final provider = cfg['provider']?.toString() ?? '';
              final model = cfg['model']?.toString() ?? '';
              final hasKey = cfg['has_api_key'] == true;
              final isCustom = cfg['is_custom'] == true;
              return Card(
                child: ListTile(
                  leading: Icon(isCustom ? Icons.person_rounded : Icons.dns_rounded, color: cs.primary),
                  title: Text('$provider / $model', style: const TextStyle(fontWeight: FontWeight.w600)),
                  subtitle: Row(children: [
                    Icon(Icons.key_rounded, size: 14, color: hasKey ? Colors.green : Colors.orange),
                    const SizedBox(width: 4),
                    Text(hasKey ? 'API key set' : 'No API key', style: TextStyle(fontSize: 12)),
                    if (isCustom) ...[const SizedBox(width: 8), const Chip(label: Text('Custom', style: TextStyle(fontSize: 10)))],
                  ]),
                  trailing: PopupMenuButton<String>(
                    onSelected: (action) {
                      if (action == 'edit') _showEditSheet(context, cfg, ref);
                      if (action == 'delete') _deleteConfig(id, ref);
                    },
                    itemBuilder: (_) => [
                      const PopupMenuItem(value: 'edit', child: ListTile(leading: Icon(Icons.edit_rounded), title: Text('Edit'), dense: true)),
                      if (isCustom) const PopupMenuItem(value: 'delete', child: ListTile(leading: Icon(Icons.delete_rounded, color: Colors.red), title: Text('Delete', style: TextStyle(color: Colors.red)), dense: true)),
                    ],
                  ),
                ),
              );
            },
          );
        },
      ),
    );
  }

  void _showEditSheet(BuildContext context, Map<String, dynamic>? existing, WidgetRef ref) {
    final nameCtrl = TextEditingController(text: existing?['id']?.toString() ?? '');
    final providerCtrl = TextEditingController(text: existing?['provider']?.toString() ?? '');
    final modelCtrl = TextEditingController(text: existing?['model']?.toString() ?? '');
    final keyCtrl = TextEditingController();
    final urlCtrl = TextEditingController(text: existing?['base_url']?.toString() ?? '');
    final isEdit = existing != null;

    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      builder: (ctx) => Padding(
        padding: EdgeInsets.fromLTRB(16, 0, 16, MediaQuery.of(ctx).viewInsets.bottom + 16),
        child: ListView(shrinkWrap: true, children: [
          Text(isEdit ? 'Edit ${existing?['id']}' : 'Add LLM Config', style: Theme.of(ctx).textTheme.titleLarge),
          const SizedBox(height: 16),
          TextField(controller: nameCtrl, decoration: const InputDecoration(labelText: 'Name', hintText: 'my-gpt4', border: OutlineInputBorder()), enabled: !isEdit),
          const SizedBox(height: 12),
          TextField(controller: providerCtrl, decoration: const InputDecoration(labelText: 'Provider', hintText: 'openai, anthropic, google, openrouter, ollama', border: OutlineInputBorder())),
          const SizedBox(height: 12),
          TextField(controller: modelCtrl, decoration: const InputDecoration(labelText: 'Model', hintText: 'gpt-4o, claude-3-5-sonnet, gemini-2.5-flash', border: OutlineInputBorder())),
          const SizedBox(height: 12),
          TextField(controller: keyCtrl, decoration: InputDecoration(labelText: isEdit ? 'New API Key (leave empty to keep)' : 'API Key (optional)', hintText: 'sk-...', border: const OutlineInputBorder()), obscureText: true),
          const SizedBox(height: 12),
          TextField(controller: urlCtrl, decoration: const InputDecoration(labelText: 'Base URL (optional)', hintText: 'https://api.openai.com/v1', border: OutlineInputBorder())),
          const SizedBox(height: 20),
          FilledButton.icon(
            onPressed: () async {
              final name = nameCtrl.text.trim();
              final provider = providerCtrl.text.trim();
              final model = modelCtrl.text.trim();
              if (name.isEmpty || provider.isEmpty || model.isEmpty) {
                ScaffoldMessenger.of(ctx).showSnackBar(const SnackBar(content: Text('Name, provider, and model are required')));
                return;
              }
              try {
                if (isEdit) {
                  await ref.read(ripClientProvider).updateLLMConfig(
                    configId: name,
                    provider: provider,
                    model: model,
                    apiKey: keyCtrl.text.trim().isEmpty ? null : keyCtrl.text.trim(),
                    baseUrl: urlCtrl.text.trim().isEmpty ? null : urlCtrl.text.trim(),
                  );
                } else {
                  await ref.read(ripClientProvider).addLLMConfig(
                    configId: name,
                    provider: provider,
                    model: model,
                    apiKey: keyCtrl.text.trim().isEmpty ? null : keyCtrl.text.trim(),
                    baseUrl: urlCtrl.text.trim().isEmpty ? null : urlCtrl.text.trim(),
                  );
                }
                ref.invalidate(gatewayLlmConfigsProvider);
                if (ctx.mounted) Navigator.pop(ctx);
              } catch (e) {
                if (ctx.mounted) ScaffoldMessenger.of(ctx).showSnackBar(SnackBar(content: Text('Failed: $e')));
              }
            },
            icon: const Icon(Icons.check_rounded),
            label: Text(isEdit ? 'Update' : 'Add'),
          ),
        ]),
      ),
    );
  }

  void _deleteConfig(String id, WidgetRef ref) async {
    final confirm = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Delete config?'),
        content: Text('Remove "$id"?'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Delete')),
        ],
      ),
    );
    if (confirm == true) {
      try {
        await ref.read(ripClientProvider).deleteLLMConfig(id);
        ref.invalidate(gatewayLlmConfigsProvider);
      } catch (e) {
        if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Failed: $e')));
      }
    }
  }
}
