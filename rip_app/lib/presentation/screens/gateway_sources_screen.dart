import 'dart:async';

import 'package:app_links/app_links.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../core/api/rip_client.dart';
import '../../core/design/app_colors.dart';
import '../providers/connection_provider.dart';
import '../providers/gateway_provider.dart';

class GatewaySourcesScreen extends ConsumerWidget {
  const GatewaySourcesScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final sources = ref.watch(gatewaySourcesProvider);
    return Scaffold(
      appBar: AppBar(
        title: const Text('Sources'),
        actions: [
          IconButton(
            tooltip: 'Add source',
            icon: const Icon(Icons.add_rounded),
            onPressed: () => _showAddSourceSheet(context, ref),
          ),
        ],
      ),
      body: sources.when(
        data: (data) {
          final items = (data['sources'] as List? ?? const [])
              .whereType<Map>()
              .map((item) => item.cast<String, dynamic>())
              .where(_visibleSource)
              .toList();
          if (items.isEmpty) {
            return _SourcesEmptyState(onAdd: () => _showAddSourceSheet(context, ref));
          }
          return RefreshIndicator(
            onRefresh: () => ref.refresh(gatewaySourcesProvider.future),
            child: ListView.separated(
              padding: const EdgeInsets.all(12),
              itemCount: items.length + 1,
              separatorBuilder: (_, __) => const SizedBox(height: 8),
              itemBuilder: (context, index) {
                if (index == items.length) {
                  return FilledButton.icon(
                    onPressed: () => _showAddSourceSheet(context, ref),
                    icon: const Icon(Icons.add_rounded),
                    label: const Text('Add source'),
                  );
                }
                return _SourceRow(
                  source: items[index],
                  onTap: () => _showSourceDetailSheet(context, ref, items[index]),
                );
              },
            ),
          );
        },
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (error, _) => Center(child: Text('Sources unavailable: $error')),
      ),
    );
  }
}

class _SourceRow extends StatelessWidget {
  const _SourceRow({required this.source, required this.onTap});

  final Map<String, dynamic> source;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final alwaysOn = source['always_on'] == true || source['protected'] == true;
    final enabled = source['enabled'] == true;
    final healthy = source['healthy'] == true;
    final oauthStatus = source['oauth_status'] as String?;
    final hints = (source['domain_hints'] as List? ?? const []).whereType<String>().toList();
    final statusIcon = _statusIcon(oauthStatus, healthy);
    final statusColor = _statusColor(oauthStatus, healthy);
    final subtitle = _subtitle(alwaysOn, enabled, oauthStatus);
    return Material(
      color: AppColors.surface,
      borderRadius: BorderRadius.circular(8),
      child: InkWell(
        borderRadius: BorderRadius.circular(8),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Row(
            children: [
              Icon(
                statusIcon,
                color: statusColor,
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      '${source['name'] ?? 'source'}',
                      style: Theme.of(context).textTheme.titleMedium,
                      overflow: TextOverflow.ellipsis,
                    ),
                    const SizedBox(height: 4),
                    Text(
                      subtitle,
                      style: Theme.of(context).textTheme.bodySmall?.copyWith(
                            color: AppColors.textSecondary,
                          ),
                    ),
                    if (hints.isNotEmpty) ...[
                      const SizedBox(height: 8),
                      Wrap(
                        spacing: 6,
                        runSpacing: 6,
                        children: hints.take(4).map((hint) => _HintChip(label: hint)).toList(),
                      ),
                    ],
                  ],
                ),
              ),
              const SizedBox(width: 10),
              if (alwaysOn)
                const Chip(label: Text('Core'))
              else if (oauthStatus == 'needs_reauth')
                const Chip(label: Text('Re-auth'))
              else if (oauthStatus == 'pending_authorization')
                const Chip(label: Text('Pending'))
              else
                Switch(
                  value: enabled,
                  onChanged: null,
                ),
            ],
          ),
        ),
      ),
    );
  }

  IconData _statusIcon(String? oauthStatus, bool healthy) {
    if (oauthStatus == 'active') return Icons.check_circle_rounded;
    if (oauthStatus == 'pending_authorization') return Icons.pending_rounded;
    if (oauthStatus == 'needs_reauth') return Icons.warning_amber_rounded;
    if (oauthStatus == 'revoked') return Icons.link_off_rounded;
    return healthy ? Icons.check_circle_rounded : Icons.error_outline_rounded;
  }

  Color _statusColor(String? oauthStatus, bool healthy) {
    if (oauthStatus == 'active') return Colors.green;
    if (oauthStatus == 'pending_authorization') return AppColors.textSecondary;
    if (oauthStatus == 'needs_reauth' || oauthStatus == 'revoked') return Colors.amber;
    return healthy ? Colors.green : Colors.amber;
  }

  String _subtitle(bool alwaysOn, bool enabled, String? oauthStatus) {
    if (alwaysOn) return 'Always on';
    if (oauthStatus == 'active') {
      return 'Connected as ${source['oauth_account_label'] ?? 'OAuth account'}';
    }
    if (oauthStatus == 'pending_authorization') return 'Waiting for authorization';
    if (oauthStatus == 'needs_reauth') return 'Needs re-authorization';
    if (oauthStatus == 'revoked') return 'Disconnected';
    return enabled ? '${source['transport'] ?? 'http'} source' : 'Disabled';
  }
}

class _HintChip extends StatelessWidget {
  const _HintChip({required this.label});

  final String label;

  @override
  Widget build(BuildContext context) {
    return Chip(
      visualDensity: VisualDensity.compact,
      label: Text(label),
      avatar: const Icon(Icons.sell_outlined, size: 14),
    );
  }
}

class _SourcesEmptyState extends StatelessWidget {
  const _SourcesEmptyState({required this.onAdd});

  final VoidCallback onAdd;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.power_rounded, size: 44, color: AppColors.primary),
            const SizedBox(height: 14),
            Text(
              'RIP is ready. Add an MCP server endpoint when you want Gateway to query another tool.',
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.bodyMedium,
            ),
            const SizedBox(height: 18),
            FilledButton.icon(
              onPressed: onAdd,
              icon: const Icon(Icons.add_rounded),
              label: const Text('Add source'),
            ),
          ],
        ),
      ),
    );
  }
}

bool _visibleSource(Map<String, dynamic> source) {
  if (source['name'] == 'rip') return true;
  return source['kind'] != 'builtin';
}

Future<void> _showSourceDetailSheet(
  BuildContext context,
  WidgetRef ref,
  Map<String, dynamic> source,
) async {
  final client = ref.read(ripClientProvider);
  await showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    builder: (context) => _SourceDetailSheet(
      source: source,
      client: client,
      onChanged: () => ref.invalidate(gatewaySourcesProvider),
    ),
  );
}

class _SourceDetailSheet extends StatefulWidget {
  const _SourceDetailSheet({
    required this.source,
    required this.client,
    required this.onChanged,
  });

  final Map<String, dynamic> source;
  final RipClient client;
  final VoidCallback onChanged;

  @override
  State<_SourceDetailSheet> createState() => _SourceDetailSheetState();
}

class _SourceDetailSheetState extends State<_SourceDetailSheet> {
  late bool _enabled;
  String? _testStatus;
  bool _busy = false;
  StreamSubscription<Uri>? _linkSub;

  @override
  void initState() {
    super.initState();
    _enabled = widget.source['enabled'] == true;
    _linkSub = AppLinks().uriLinkStream.listen(_handleOAuthCallback);
  }

  @override
  void dispose() {
    _linkSub?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final protected = widget.source['protected'] == true || widget.source['always_on'] == true;
    final sourceId = '${widget.source['id'] ?? widget.source['name']}';
    final hints = (widget.source['domain_hints'] as List? ?? const []).whereType<String>().toList();
    final capabilityTools = _capabilityToolNames(widget.source);
    final isOAuth = widget.source['auth_type'] == 'oauth2';
    final oauthStatus = widget.source['oauth_status'] as String?;
    return SafeArea(
      child: Padding(
        padding: EdgeInsets.only(
          left: 16,
          right: 16,
          top: 16,
          bottom: MediaQuery.of(context).viewInsets.bottom + 16,
        ),
        child: SingleChildScrollView(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              Text('${widget.source['name']}', style: Theme.of(context).textTheme.titleLarge),
              const SizedBox(height: 6),
              Text(
                _sourceAddress(widget.source),
                style: Theme.of(context).textTheme.bodySmall?.copyWith(color: AppColors.textSecondary),
              ),
              const SizedBox(height: 16),
              Wrap(spacing: 6, runSpacing: 6, children: hints.map((hint) => _HintChip(label: hint)).toList()),
              if (capabilityTools.isNotEmpty) ...[
                const SizedBox(height: 12),
                Text(
                  'Tools: ${capabilityTools.take(5).join(', ')}',
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(color: AppColors.textSecondary),
                  overflow: TextOverflow.ellipsis,
                  maxLines: 2,
                ),
              ],
              const SizedBox(height: 16),
              SwitchListTile(
                contentPadding: EdgeInsets.zero,
                title: Text(protected ? 'Always on' : 'Enabled'),
                value: protected || _enabled,
                onChanged: protected || _busy ? null : (value) => _setEnabled(sourceId, value),
              ),
              if (isOAuth) ...[
                ListTile(
                  contentPadding: EdgeInsets.zero,
                  leading: const Icon(Icons.verified_user_rounded),
                  title: const Text('Connected as'),
                  subtitle: Text('${widget.source['oauth_account_label'] ?? 'Pending authorization'}'),
                ),
                ListTile(
                  contentPadding: EdgeInsets.zero,
                  leading: Icon(
                    oauthStatus == 'active'
                        ? Icons.check_circle_rounded
                        : Icons.warning_amber_rounded,
                    color: oauthStatus == 'active' ? Colors.green : Colors.amber,
                  ),
                  title: const Text('Status'),
                  subtitle: Text(oauthStatus ?? 'pending_authorization'),
                  trailing: TextButton(
                    onPressed: _busy ? null : () => _reauthorize(sourceId),
                    child: const Text('Re-authorize'),
                  ),
                ),
              ] else
                ListTile(
                  contentPadding: EdgeInsets.zero,
                  leading: const Icon(Icons.vpn_key_rounded),
                  title: const Text('Credential'),
                  subtitle: Text('${widget.source['credential_mask'] ?? 'No credential saved'}'),
                  trailing: TextButton(
                    onPressed: _busy ? null : () => _replaceCredential(sourceId),
                    child: const Text('Replace'),
                  ),
                ),
              if (!isOAuth)
                FilledButton.icon(
                  onPressed: _busy ? null : () => _test(sourceId),
                  icon: _busy
                      ? const SizedBox.square(
                          dimension: 18,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : const Icon(Icons.cable_rounded),
                  label: const Text('Test connection'),
                )
              else
                FilledButton.icon(
                  onPressed: _busy ? null : () => _reauthorize(sourceId),
                  icon: const Icon(Icons.login_rounded),
                  label: const Text('Re-authorize'),
                ),
              if (isOAuth) ...[
                const SizedBox(height: 10),
                OutlinedButton.icon(
                  onPressed: _busy ? null : () => _disconnectOAuth(sourceId),
                  icon: const Icon(Icons.link_off_rounded),
                  label: const Text('Disconnect'),
                ),
              ],
              if (_testStatus != null) ...[
                const SizedBox(height: 10),
                _TestStatus(status: _testStatus!),
              ],
              const SizedBox(height: 12),
              if (!protected)
                OutlinedButton.icon(
                  onPressed: _busy ? null : () => _remove(sourceId),
                  icon: const Icon(Icons.delete_outline_rounded),
                  label: const Text('Remove source'),
                ),
            ],
          ),
        ),
      ),
    );
  }

  Future<void> _setEnabled(String sourceId, bool value) async {
    setState(() => _busy = true);
    try {
      await widget.client.updateGatewaySource(sourceId, {'enabled': value});
      setState(() => _enabled = value);
      widget.onChanged();
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _test(String sourceId) async {
    setState(() => _busy = true);
    try {
      final result = await widget.client.testGatewaySource(sourceId);
      setState(() => _testStatus = '${result['status'] ?? 'unreachable'}');
      widget.onChanged();
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _replaceCredential(String sourceId) async {
    final controller = TextEditingController();
    final credential = await showDialog<String>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Replace credential'),
        content: TextField(
          controller: controller,
          obscureText: true,
          decoration: const InputDecoration(labelText: 'New token or secret'),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.pop(context, controller.text), child: const Text('Replace')),
        ],
      ),
    );
    if (credential == null || credential.trim().isEmpty) return;
    await widget.client.replaceGatewaySourceCredential(sourceId, credential.trim());
    widget.onChanged();
  }

  Future<void> _reauthorize(String sourceId) async {
    setState(() => _busy = true);
    try {
      final result = await widget.client.reauthorizeGatewaySourceOAuth(sourceId, {
        'redirect_uri': 'riplink://oauth/callback',
        'client_type': 'mobile',
        'requested_by': 'mobile',
      });
      final url = Uri.parse('${result['authorize_url']}');
      await launchUrl(url, mode: LaunchMode.externalApplication);
      setState(() => _testStatus = 'waiting_for_authorization');
      widget.onChanged();
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _disconnectOAuth(String sourceId) async {
    final name = '${widget.source['name']}';
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text('Disconnect $name?'),
        content: Text('Disconnect $name? RIP will stop checking it in every answer.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.pop(context, true), child: const Text('Disconnect')),
        ],
      ),
    );
    if (confirmed != true) return;
    await widget.client.revokeGatewaySourceOAuth(sourceId);
    widget.onChanged();
    if (mounted) Navigator.pop(context);
  }

  Future<void> _handleOAuthCallback(Uri uri) async {
    if (uri.scheme != 'riplink' || uri.host != 'oauth' || uri.path != '/callback') return;
    final code = uri.queryParameters['code'];
    final state = uri.queryParameters['state'];
    final error = uri.queryParameters['error'];
    if (error != null && error.isNotEmpty) {
      setState(() => _testStatus = 'authorization_cancelled');
      return;
    }
    if (code == null || state == null) return;
    setState(() => _busy = true);
    try {
      await widget.client.completeGatewayOAuth({
        'code': code,
        'state': state,
        'requested_by': 'mobile',
      });
      setState(() => _testStatus = 'ok');
      widget.onChanged();
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _remove(String sourceId) async {
    final name = '${widget.source['name']}';
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text('Remove $name?'),
        content: Text('Remove $name? RIP will stop checking it in every answer.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.pop(context, true), child: const Text('Remove')),
        ],
      ),
    );
    if (confirmed != true) return;
    await widget.client.deleteGatewaySource(sourceId);
    widget.onChanged();
    if (mounted) Navigator.pop(context);
  }
}

List<String> _capabilityToolNames(Map<String, dynamic> source) {
  final capabilities = (source['capabilities'] as Map?)?.cast<String, dynamic>();
  final tools = capabilities?['tools'] as List?;
  if (tools == null) return const [];
  return tools
      .whereType<Map>()
      .map((tool) => '${tool['name'] ?? ''}'.trim())
      .where((name) => name.isNotEmpty)
      .toList();
}

class _TestStatus extends StatelessWidget {
  const _TestStatus({required this.status});

  final String status;

  @override
  Widget build(BuildContext context) {
    final ok = status == 'ok';
    return Row(
      children: [
        Icon(ok ? Icons.check_circle_rounded : Icons.warning_amber_rounded, color: ok ? Colors.green : Colors.amber),
        const SizedBox(width: 8),
        Expanded(
          child: Text(ok ? 'Connected' : 'Needs attention: $status'),
        ),
      ],
    );
  }
}

String _sourceAddress(Map<String, dynamic> source) {
  final transport = '${source['transport'] ?? 'streamable_http'}';
  final config = (source['mcp_config'] as Map?)?.cast<String, dynamic>() ?? <String, dynamic>{};
  if (transport == 'stdio') {
    return 'stdio • ${config['stdio_command'] ?? 'server command'}';
  }
  return '$transport • ${source['endpoint_url'] ?? 'no endpoint'}';
}

List<String> _splitArgs(String value) {
  return value
      .split(RegExp(r'\s+'))
      .map((item) => item.trim())
      .where((item) => item.isNotEmpty)
      .toList();
}

Map<String, String> _parseEnv(String value) {
  final env = <String, String>{};
  for (final line in value.split('\n')) {
    final trimmed = line.trim();
    if (trimmed.isEmpty || !trimmed.contains('=')) continue;
    final index = trimmed.indexOf('=');
    final key = trimmed.substring(0, index).trim();
    final val = trimmed.substring(index + 1).trim();
    if (key.isNotEmpty) env[key] = val;
  }
  return env;
}

Future<void> _showAddSourceSheet(BuildContext context, WidgetRef ref) async {
  final client = ref.read(ripClientProvider);
  await showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    builder: (context) => _AddSourceSheet(
      client: client,
      onSaved: () => ref.invalidate(gatewaySourcesProvider),
    ),
  );
}

class _AddSourceSheet extends StatefulWidget {
  const _AddSourceSheet({required this.client, required this.onSaved});

  final RipClient client;
  final VoidCallback onSaved;

  @override
  State<_AddSourceSheet> createState() => _AddSourceSheetState();
}

class _AddSourceSheetState extends State<_AddSourceSheet> {
  final _name = TextEditingController();
  final _endpoint = TextEditingController();
  final _stdioCommand = TextEditingController();
  final _stdioArgs = TextEditingController();
  final _stdioCwd = TextEditingController();
  final _stdioEnv = TextEditingController();
  final _credential = TextEditingController();
  final _toolName = TextEditingController(text: 'search');
  final _hints = <String>{};
  String _transport = 'streamable_http';
  String _authType = 'bearer';
  String? _testStatus;
  bool _busy = false;

  static const _domainHints = ['payments', 'auth', 'infra', 'docs', 'notifications', 'database', 'api'];

  @override
  void dispose() {
    _name.dispose();
    _endpoint.dispose();
    _stdioCommand.dispose();
    _stdioArgs.dispose();
    _stdioCwd.dispose();
    _stdioEnv.dispose();
    _credential.dispose();
    _toolName.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      child: Padding(
        padding: EdgeInsets.only(
          left: 14,
          right: 14,
          top: 14,
          bottom: MediaQuery.of(context).viewInsets.bottom + 14,
        ),
        child: SingleChildScrollView(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              Row(
                children: [
                  const Icon(Icons.hub_rounded, color: AppColors.primary),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Text(
                      'Add MCP server',
                      style: Theme.of(context).textTheme.titleLarge,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 12),
              TextField(controller: _name, decoration: const InputDecoration(labelText: 'Name')),
              const SizedBox(height: 10),
              SegmentedButton<String>(
                segments: const [
                  ButtonSegment(value: 'streamable_http', label: Text('HTTP')),
                  ButtonSegment(value: 'sse', label: Text('SSE')),
                  ButtonSegment(value: 'stdio', label: Text('stdio')),
                ],
                selected: {_transport},
                onSelectionChanged: (value) => setState(() => _transport = value.first),
              ),
              const SizedBox(height: 10),
              if (_transport == 'stdio') ...[
                TextField(controller: _stdioCommand, decoration: const InputDecoration(labelText: 'Server command')),
                const SizedBox(height: 10),
                TextField(controller: _stdioArgs, decoration: const InputDecoration(labelText: 'Arguments')),
                const SizedBox(height: 10),
                TextField(controller: _stdioCwd, decoration: const InputDecoration(labelText: 'Working directory, optional')),
                const SizedBox(height: 10),
                TextField(
                  controller: _stdioEnv,
                  minLines: 2,
                  maxLines: 4,
                  decoration: const InputDecoration(labelText: 'Environment, KEY=value per line'),
                ),
              ] else
                TextField(controller: _endpoint, decoration: const InputDecoration(labelText: 'MCP endpoint URL')),
              const SizedBox(height: 10),
              DropdownButtonFormField<String>(
                value: _authType,
                decoration: const InputDecoration(labelText: 'Auth type'),
                items: const [
                  DropdownMenuItem(value: 'bearer', child: Text('Bearer token')),
                  DropdownMenuItem(value: 'api_key', child: Text('API key')),
                  DropdownMenuItem(value: 'none', child: Text('None')),
                ],
                onChanged: (value) => setState(() => _authType = value ?? 'bearer'),
              ),
              const SizedBox(height: 10),
              TextField(
                controller: _credential,
                obscureText: true,
                decoration: const InputDecoration(labelText: 'Credential, optional'),
              ),
              const SizedBox(height: 10),
              TextField(controller: _toolName, decoration: const InputDecoration(labelText: 'Tool name')),
              const SizedBox(height: 14),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: _domainHints.map((hint) {
                  return FilterChip(
                    label: Text(hint),
                    selected: _hints.contains(hint),
                    onSelected: (selected) => setState(() {
                      if (selected) {
                        _hints.add(hint);
                      } else {
                        _hints.remove(hint);
                      }
                    }),
                  );
                }).toList(),
              ),
              const SizedBox(height: 16),
              Row(
                children: [
                  Expanded(
                    child: OutlinedButton.icon(
                      onPressed: _busy ? null : _testDraft,
                      icon: const Icon(Icons.cable_rounded),
                      label: const Text('Test'),
                    ),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: FilledButton.icon(
                      onPressed: _busy || _testStatus != 'ok' ? null : _save,
                      icon: const Icon(Icons.save_rounded),
                      label: const Text('Save'),
                    ),
                  ),
                ],
              ),
              if (_testStatus != null) ...[
                const SizedBox(height: 10),
                _TestStatus(status: _testStatus!),
              ],
            ],
          ),
        ),
      ),
    );
  }

  Map<String, dynamic> _payload() {
    final payload = <String, dynamic>{
      'name': _name.text.trim(),
      'kind': 'mcp',
      'transport': _transport,
      'auth_type': _authType,
      'tool_name': _toolName.text.trim().isEmpty ? 'search' : _toolName.text.trim(),
      if (_credential.text.trim().isNotEmpty) 'credential': _credential.text.trim(),
      'domain_hints': _hints.toList(),
      'priority_hint': 50,
      'enabled': true,
    };
    if (_transport == 'stdio') {
      payload['stdio_command'] = _stdioCommand.text.trim();
      payload['stdio_args'] = _splitArgs(_stdioArgs.text);
      if (_stdioCwd.text.trim().isNotEmpty) payload['stdio_cwd'] = _stdioCwd.text.trim();
      final env = _parseEnv(_stdioEnv.text);
      if (env.isNotEmpty) payload['stdio_env'] = env;
    } else {
      payload['endpoint_url'] = _endpoint.text.trim();
    }
    return payload;
  }

  Future<void> _testDraft() async {
    if (_name.text.trim().isEmpty) return;
    if (_transport == 'stdio' && _stdioCommand.text.trim().isEmpty) return;
    if (_transport != 'stdio' && _endpoint.text.trim().isEmpty) return;
    setState(() => _busy = true);
    try {
      final created = await widget.client.createGatewaySource({..._payload(), 'enabled': false});
      final result = await widget.client.testGatewaySource('${created['id']}');
      await widget.client.deleteGatewaySource('${created['id']}');
      setState(() => _testStatus = '${result['status'] ?? 'unreachable'}');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _save() async {
    setState(() => _busy = true);
    try {
      final created = await widget.client.createGatewaySource(_payload());
      final result = await widget.client.testGatewaySource('${created['id']}');
      if ('${result['status']}' != 'ok') {
        setState(() => _testStatus = '${result['status'] ?? 'unreachable'}');
        return;
      }
      widget.onSaved();
      if (mounted) Navigator.pop(context);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }
}
