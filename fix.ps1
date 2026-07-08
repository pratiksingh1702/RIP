# ============================================================
# FIX: Integrate LLM Configurations into Ask AI Block (Windows)
# ============================================================

# 1. BACKUP the original file first
Copy-Item lib\screens\workflows_screen.dart lib\screens\workflows_screen.dart.backup

# 2. CREATE the LLM configs provider in gateway_provider.dart
@'
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../clients/rip_client.dart';
import '../data/models/connection.dart';

final ripClientProvider = Provider<RipClient>((ref) {
  final connection = ref.watch(connectionProvider);
  return RipClient(serverUrl: connection.serverUrl, apiKey: connection.apiKey);
});

final gatewayWorkflowsProvider = FutureProvider<List<dynamic>>((ref) async {
  final client = ref.watch(ripClientProvider);
  return await client.gatewayWorkflows();
});

final gatewayPromptTemplatesProvider = FutureProvider<Map<String, dynamic>>((ref) async {
  final client = ref.watch(ripClientProvider);
  return await client.gatewayPromptTemplates();
});

// ADDED: LLM Configs Provider
final gatewayLlmConfigsProvider = FutureProvider<Map<String, dynamic>>((ref) async {
  final client = ref.watch(ripClientProvider);
  return await client.listLLMConfigs();
});
'@ | Out-File -Encoding utf8 lib\providers\gateway_provider.dart

# 3. Read the current file
$content = Get-Content lib\screens\workflows_screen.dart -Raw

# 4. FIX: Update _QuickConfigSheet
$quickConfigPattern = '(?s)class _QuickConfigSheet \{[^}]*?\n\}'
$quickConfigReplacement = @'
class _QuickConfigSheet {
  static Future<_Configured?> show(BuildContext ctx, Map<String, dynamic> block,
      List<Map<String, dynamic>> existing, WidgetRef ref) {
    final bid = block['id']?.toString() ?? '';
    
    // FIX: Check for prompt/LLM blocks FIRST
    if (bid.contains('prompt') || 
        bid.toLowerCase().contains('llm') || 
        bid.toLowerCase().contains('ask_ai') ||
        bid.toLowerCase().contains('ai_analysis') ||
        bid == 'prompt.ask_ai') {
      return showModalBottomSheet<_Configured>(
        context: ctx,
        isScrollControlled: true,
        showDragHandle: true,
        builder: (_) => _PromptQuickConfig(ref: ref),
      );
    }
    
    // Rest of existing checks...
    if (bid.toLowerCase().contains('rip') ||
        bid.toLowerCase().contains('context')) return _RIPQuickConfig();
    if (bid.contains('approval')) return _ApprovalQuickConfig();
    if (bid.contains('terminal')) return _TerminalQuickConfig();
    if (bid.contains('notification')) return _NotificationQuickConfig();
    return _GenericQuickConfig(block: block);
  }
}
'@

$content = $content -replace $quickConfigPattern, $quickConfigReplacement

# 5. FIX: Replace _PromptQuickConfig
$promptConfigPattern = '(?s)class _PromptQuickConfig[^}]*?\n\}'
$promptConfigReplacement = @'
class _PromptQuickConfig extends ConsumerStatefulWidget {
  const _PromptQuickConfig({required this.ref});
  final WidgetRef ref;
  @override
  ConsumerState<_PromptQuickConfig> createState() => _PromptQuickConfigState();
}

class _PromptQuickConfigState extends ConsumerState<_PromptQuickConfig> {
  String? _selectedTemplateId;
  String? _selectedLlmConfigId;
  final _quick = TextEditingController();
  String _provider = 'openai';
  String _model = 'gpt-4';

  @override
  void dispose() {
    _quick.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final prompts = widget.ref.watch(gatewayPromptTemplatesProvider);
    final llmConfigs = widget.ref.watch(gatewayLlmConfigsProvider);
    final cs = Theme.of(context).colorScheme;

    return Padding(
      padding: EdgeInsets.fromLTRB(
          16, 0, 16, MediaQuery.viewInsetsOf(context).bottom + 16),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(children: [
            const Icon(Icons.psychology_rounded, color: Color(0xFF8B5CF6)),
            const SizedBox(width: 10),
            Expanded(
                child: Text('Ask AI',
                    style: Theme.of(context).textTheme.titleLarge)),
          ]),
          const SizedBox(height: 12),
          _buildLlmConfigSelector(cs),
          const Divider(height: 16),
          Flexible(
            child: prompts.when(
              data: (d) {
                final templates = ((d['templates'] as List?) ?? [])
                    .whereType<Map>()
                    .map((m) => Map<String, dynamic>.from(m))
                    .toList();
                if (templates.isEmpty) {
                  return const Text('No saved templates yet.');
                }
                return Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('Saved Templates',
                        style: Theme.of(context).textTheme.titleSmall),
                    const SizedBox(height: 6),
                    Expanded(
                      child: ListView(
                        shrinkWrap: true,
                        children: templates.map((t) => _buildTemplateCard(t, cs)).toList(),
                      ),
                    ),
                  ],
                );
              },
              loading: () => const Expanded(
                child: Center(child: CircularProgressIndicator()),
              ),
              error: (e, _) => Expanded(
                child: Center(child: Text('Error loading templates: $e')),
              ),
            ),
          ),
          const Divider(height: 16),
          Text('Quick Prompt',
              style: Theme.of(context).textTheme.titleSmall),
          const SizedBox(height: 6),
          TextField(
            controller: _quick,
            minLines: 2,
            maxLines: 4,
            decoration: const InputDecoration(
              hintText: 'Analyze this code...',
              border: OutlineInputBorder(),
              filled: true,
            ),
          ),
          const SizedBox(height: 12),
          Row(children: [
            Expanded(
              child: FilledButton.icon(
                onPressed: _canAdd()
                    ? () {
                        final b = _buildBindings();
                        Navigator.pop(context,
                            _Configured(config: _buildConfig(), bindings: b));
                      }
                    : null,
                icon: const Icon(Icons.check_rounded),
                label: const Text('Add Block'),
              ),
            ),
            const SizedBox(width: 8),
            OutlinedButton.icon(
              onPressed: () => Navigator.pop(context),
              icon: const Icon(Icons.close_rounded),
              label: const Text('Cancel'),
            ),
          ]),
        ],
      ),
    );
  }

  Widget _buildLlmConfigSelector(ColorScheme cs) {
    final llmConfigs = widget.ref.watch(gatewayLlmConfigsProvider);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            const Icon(Icons.settings_rounded, size: 16, color: Color(0xFF8B5CF6)),
            const SizedBox(width: 6),
            Text('LLM Configuration',
                style: Theme.of(context).textTheme.titleSmall),
            const Spacer(),
            TextButton.icon(
              onPressed: () => _showAddLlmConfigDialog(),
              icon: const Icon(Icons.add_rounded, size: 16),
              label: const Text('Add'),
              style: TextButton.styleFrom(
                visualDensity: VisualDensity.compact,
              ),
            ),
          ],
        ),
        const SizedBox(height: 6),
        llmConfigs.when(
          data: (configs) {
            final configList = configs is Map && configs['configs'] is List
                ? (configs['configs'] as List)
                    .whereType<Map>()
                    .map((m) => Map<String, dynamic>.from(m))
                    .toList()
                : [];

            if (configList.isEmpty) {
              return Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: cs.surfaceContainerHighest,
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Row(
                  children: [
                    Icon(Icons.info_outline_rounded, size: 18, color: cs.outline),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        'No LLM configs found. Add one to customize your AI provider.',
                        style: Theme.of(context).textTheme.bodySmall,
                      ),
                    ),
                  ],
                ),
              );
            }

            return Wrap(
              spacing: 6,
              runSpacing: 6,
              children: [
                ChoiceChip(
                  label: const Text('Default (OpenAI)'),
                  selected: _selectedLlmConfigId == null,
                  onSelected: (sel) => setState(() {
                    _selectedLlmConfigId = null;
                    _provider = 'openai';
                    _model = 'gpt-4';
                  }),
                  selectedColor: cs.primaryContainer,
                  avatar: const Icon(Icons.cloud_rounded, size: 14),
                ),
                ...configList.map((cfg) {
                  final id = cfg['config_id']?.toString() ?? '';
                  final provider = cfg['provider']?.toString() ?? 'unknown';
                  final model = cfg['model']?.toString() ?? 'model';
                  final isSelected = _selectedLlmConfigId == id;
                  return ChoiceChip(
                    label: Text('$provider: $model',
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis),
                    selected: isSelected,
                    onSelected: (sel) => setState(() {
                      if (sel) {
                        _selectedLlmConfigId = id;
                        _provider = provider;
                        _model = model;
                      } else {
                        _selectedLlmConfigId = null;
                        _provider = 'openai';
                        _model = 'gpt-4';
                      }
                    }),
                    selectedColor: cs.primaryContainer,
                    avatar: Icon(Icons.memory_rounded, size: 14),
                  );
                }).toList(),
              ],
            );
          },
          loading: () => const SizedBox(
            height: 30,
            child: Center(
              child: SizedBox.square(
                dimension: 20,
                child: CircularProgressIndicator(strokeWidth: 2),
              ),
            ),
          ),
          error: (e, _) => Text('Error: $e',
              style: TextStyle(color: cs.error, fontSize: 12)),
        ),
      ],
    );
  }

  Widget _buildTemplateCard(Map<String, dynamic> t, ColorScheme cs) {
    final tid = t['id']?.toString() ?? '';
    final sel = _selectedTemplateId == tid;
    return Card(
      margin: const EdgeInsets.only(bottom: 6),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(8),
        side: BorderSide(
          color: sel ? cs.primary : cs.outlineVariant,
          width: sel ? 2 : 1,
        ),
      ),
      child: InkWell(
        borderRadius: BorderRadius.circular(8),
        onTap: () => setState(() => _selectedTemplateId = sel ? null : tid),
        child: Padding(
          padding: const EdgeInsets.all(10),
          child: Row(
            children: [
              Container(
                width: 20,
                height: 20,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: sel ? cs.primary : Colors.transparent,
                  border: Border.all(
                    color: sel ? cs.primary : cs.outline,
                    width: 2,
                  ),
                ),
                child: sel
                    ? Icon(Icons.check_rounded, size: 12, color: cs.onPrimary)
                    : null,
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      '${t['name'] ?? 'Untitled'}',
                      style: Theme.of(context).textTheme.titleSmall,
                    ),
                    Text(
                      '${t['prompt_template'] ?? t['template'] ?? ''}'
                          .replaceAll(RegExp(r'\s+'), ' ')
                          .trim(),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: Theme.of(context)
                          .textTheme
                          .bodySmall
                          ?.copyWith(fontSize: 10),
                    ),
                  ],
                ),
              ),
              if (t['visibility'] == 'public')
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 2),
                  decoration: BoxDecoration(
                    color: cs.primaryContainer,
                    borderRadius: BorderRadius.circular(4),
                  ),
                  child: Text('Public',
                      style: TextStyle(fontSize: 8, color: cs.primary)),
                ),
            ],
          ),
        ),
      ),
    );
  }

  Map<String, dynamic> _buildBindings() {
    final b = <String, dynamic>{
      'query': {'source': 'trigger_query'}
    };

    if (_selectedTemplateId != null) {
      b['prompt_id'] = {'source': 'literal', 'value': _selectedTemplateId};
    } else if (_quick.text.trim().isNotEmpty) {
      b['prompt'] = {'source': 'literal', 'value': _quick.text.trim()};
    }

    if (_selectedLlmConfigId != null) {
      b['llm_config'] = {'source': 'literal', 'value': _selectedLlmConfigId};
    }

    return b;
  }

  Map<String, dynamic> _buildConfig() {
    final config = <String, dynamic>{};

    if (_selectedLlmConfigId != null) {
      config['llm_config_id'] = _selectedLlmConfigId;
    } else {
      config['provider'] = _provider;
      config['model'] = _model;
    }

    return config;
  }

  bool _canAdd() {
    return _selectedTemplateId != null || _quick.text.trim().isNotEmpty;
  }

  Future<void> _showAddLlmConfigDialog() async {
    final provider = TextEditingController(text: 'openai');
    final model = TextEditingController(text: 'gpt-4');
    final apiKey = TextEditingController();
    final baseUrl = TextEditingController();
    final configId = TextEditingController();

    await showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Add LLM Configuration'),
        content: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextField(
                controller: configId,
                decoration: const InputDecoration(
                  labelText: 'Config ID (unique name)',
                  hintText: 'my-openai-config',
                ),
              ),
              const SizedBox(height: 8),
              TextField(
                controller: provider,
                decoration: const InputDecoration(
                  labelText: 'Provider',
                  hintText: 'openai, anthropic, deepseek, etc.',
                ),
              ),
              const SizedBox(height: 8),
              TextField(
                controller: model,
                decoration: const InputDecoration(
                  labelText: 'Model',
                  hintText: 'gpt-4, claude-3, etc.',
                ),
              ),
              const SizedBox(height: 8),
              TextField(
                controller: apiKey,
                decoration: const InputDecoration(
                  labelText: 'API Key',
                  hintText: 'sk-...',
                ),
                obscureText: true,
              ),
              const SizedBox(height: 8),
              TextField(
                controller: baseUrl,
                decoration: const InputDecoration(
                  labelText: 'Base URL (optional)',
                  hintText: 'https://api.openai.com/v1',
                ),
              ),
            ],
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () async {
              if (configId.text.trim().isEmpty) return;

              try {
                await ref.read(ripClientProvider).addLLMConfig(
                      configId: configId.text.trim(),
                      provider: provider.text.trim(),
                      model: model.text.trim(),
                      apiKey: apiKey.text.trim().isNotEmpty
                          ? apiKey.text.trim()
                          : null,
                      baseUrl: baseUrl.text.trim().isNotEmpty
                          ? baseUrl.text.trim()
                          : null,
                    );
                ref.invalidate(gatewayLlmConfigsProvider);
                if (mounted) Navigator.pop(ctx);
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(content: Text('LLM config added successfully!')),
                );
              } catch (e) {
                if (mounted) {
                  ScaffoldMessenger.of(context).showSnackBar(
                    SnackBar(content: Text('Failed to add config: $e')),
                  );
                }
              }
            },
            child: const Text('Add'),
          ),
        ],
      ),
    );
  }
}
'@

$content = $content -replace $promptConfigPattern, $promptConfigReplacement

# 6. Save the file
$content | Out-File -Encoding utf8 lib\screens\workflows_screen.dart

# 7. Format the code
dart format lib\screens\workflows_screen.dart
dart format lib\providers\gateway_provider.dart

# 8. Analyze
flutter analyze lib\screens\workflows_screen.dart

Write-Host ""
Write-Host "============================================================"
Write-Host "FIXES APPLIED SUCCESSFULLY!"
Write-Host "============================================================"
Write-Host ""
Write-Host "Changes made:"
Write-Host "1. Added gatewayLlmConfigsProvider to gateway_provider.dart"
Write-Host "2. Updated _QuickConfigSheet to detect prompt/LLM blocks"
Write-Host "3. Enhanced _PromptQuickConfig with LLM configuration selector"
Write-Host "4. Added ability to add custom LLM configurations"
Write-Host ""
Write-Host "To test:"
Write-Host "1. Run 'flutter pub get' if needed"
Write-Host "2. Run 'flutter run'"
Write-Host "3. Navigate to Workflows > Add Block > Ask AI"
Write-Host "4. You should see LLM Configuration selector"
Write-Host ""
Write-Host "If you encounter issues, restore backup:"
Write-Host "Copy-Item lib\screens\workflows_screen.dart.backup lib\screens\workflows_screen.dart"