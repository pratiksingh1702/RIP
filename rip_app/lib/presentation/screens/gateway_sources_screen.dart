import 'dart:async';

import 'package:app_links/app_links.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../core/api/rip_client.dart';
import '../../core/design/app_colors.dart';
import '../../data/models/project.dart';
import '../providers/connection_provider.dart';
import '../providers/gateway_provider.dart';
import '../providers/project_provider.dart';
import '../widgets/overlays/add_repo_sheet.dart';

import 'mcp_marketplace_screen.dart';

class GatewaySourcesScreen extends ConsumerStatefulWidget {
  const GatewaySourcesScreen({super.key});

  @override
  ConsumerState<GatewaySourcesScreen> createState() => _GatewaySourcesScreenState();
}

class _GatewaySourcesScreenState extends ConsumerState<GatewaySourcesScreen> {
  StreamSubscription<Uri>? _linkSub;
  String? _busySourceId;
  String? _statusText;

  @override
  void initState() {
    super.initState();
    _linkSub = AppLinks().uriLinkStream.listen(_handleOAuthCallback);
  }

  @override
  void dispose() {
    _linkSub?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final sourcesAsync = ref.watch(gatewaySourcesProvider);
    final activeProjectAsync = ref.watch(activeProjectProvider);
    final projectsAsync = ref.watch(projectListProvider);

    final isDark = Theme.of(context).brightness == Brightness.dark;
    final bgColor = isDark ? const Color(0xFF0D0D12) : const Color(0xFFF8F9FA);
    final cardBgColor = isDark ? const Color(0xFF14141A) : Colors.white;
    final textColor = isDark ? Colors.white : AppColors.textPrimary;
    final mutedTextColor = isDark ? Colors.white54 : AppColors.textSecondary;

    final mediaQuery = MediaQuery.of(context);
    final topPadding = mediaQuery.padding.top;
    final bottomPadding = mediaQuery.padding.bottom;

    return Scaffold(
      extendBodyBehindAppBar: true,
      backgroundColor: bgColor,
      body: Stack(
        children: [
          // 1. SCRAWLABLE BODY CONTENT WITH REFRESH INDICATOR
          Positioned.fill(
            child: ColoredBox(
              color: bgColor,
              child: RefreshIndicator(
                color: AppColors.primary,
                backgroundColor: isDark ? const Color(0xFF1F1F28) : Colors.white,
                onRefresh: () async {
                  ref.invalidate(gatewaySourcesProvider);
                  ref.invalidate(projectListProvider);
                  await ref.read(gatewaySourcesProvider.future);
                },
                child: SingleChildScrollView(
                  physics: const BouncingScrollPhysics(parent: AlwaysScrollableScrollPhysics()),
                  padding: EdgeInsets.fromLTRB(
                    16,
                    topPadding + 76,
                    16,
                    bottomPadding + 40,
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      // --- ACTIVE PROJECT PANEL ---
                      activeProjectAsync.when(
                        data: (project) => _ProjectPanel(
                          project: project,
                          onAddRepo: _showAddRepo,
                          isDark: isDark,
                          cardBgColor: cardBgColor,
                          textColor: textColor,
                          mutedTextColor: mutedTextColor,
                        ),
                        loading: () => _LoadingPanel(isDark: isDark, cardBgColor: cardBgColor),
                        error: (error, _) => _ErrorPanel(
                          message: 'Projects unavailable: $error',
                          isDark: isDark,
                          cardBgColor: cardBgColor,
                        ),
                      ),

                      if (_statusText != null) ...[
                        const SizedBox(height: 12),
                        _StatusBanner(message: _statusText!, isDark: isDark),
                      ],

                      const SizedBox(height: 20),

                      // --- SECTION 1: ACCOUNT INTEGRATIONS ---
                      _SectionLabel(
                        title: 'ACCOUNT INTEGRATIONS',
                        icon: Icons.vpn_key_rounded,
                        isDark: isDark,
                      ),
                      const SizedBox(height: 8),

                      sourcesAsync.when(
                        data: (data) {
                          final sources = _orderedSources(data);
                          final accountSources = sources.where(_isAccountIntegration).toList();
                          if (accountSources.isEmpty) {
                            return _EmptyPanel(
                              title: 'No account integrations',
                              message: 'Gateway did not return GitHub, Jira, or Slack yet. Restart the server if you just updated it.',
                              isDark: isDark,
                              cardBgColor: cardBgColor,
                              mutedTextColor: mutedTextColor,
                            );
                          }
                          return Column(
                            children: [
                              for (final source in accountSources) ...[
                                _IntegrationCard(
                                  source: source,
                                  busy: _busySourceId == _sourceId(source),
                                  onConnect: () => _connectOAuth(source),
                                  onUseToken: () => _useToken(source),
                                  onReconnect: () => _connectOAuth(source),
                                  onDisconnect: () => _disconnect(source),
                                  onAllocate: () => _showAllocationSheet(source),
                                  isDark: isDark,
                                  cardBgColor: cardBgColor,
                                  textColor: textColor,
                                  mutedTextColor: mutedTextColor,
                                ),
                                const SizedBox(height: 10),
                              ],
                            ],
                          );
                        },
                        loading: () => _LoadingPanel(isDark: isDark, cardBgColor: cardBgColor),
                        error: (error, _) => _ErrorPanel(
                          message: 'Integrations unavailable: $error',
                          isDark: isDark,
                          cardBgColor: cardBgColor,
                        ),
                      ),

                      const SizedBox(height: 24),

                      // --- SECTION 2: PROJECT MCP TOOLS ---
                      _SectionLabel(
                        title: 'PROJECT MCP TOOLS',
                        icon: Icons.hub_rounded,
                        isDark: isDark,
                      ),
                      const SizedBox(height: 8),

                      projectsAsync.when(
                        data: (projects) => _CustomToolsSection(
                          hasProjects: projects.isNotEmpty,
                          sourcesAsync: sourcesAsync,
                          onAdd: _showCustomMcpSheet,
                          onReplaceCredential: _useToken,
                          onTest: _testCustomSource,
                          isDark: isDark,
                          cardBgColor: cardBgColor,
                          textColor: textColor,
                          mutedTextColor: mutedTextColor,
                        ),
                        loading: () => _LoadingPanel(isDark: isDark, cardBgColor: cardBgColor),
                        error: (error, _) => _ErrorPanel(
                          message: 'Projects unavailable: $error',
                          isDark: isDark,
                          cardBgColor: cardBgColor,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ),

          // 2. TOP FADE GRADIENT OVERLAY
          Positioned(
            top: 0,
            left: 0,
            right: 0,
            height: topPadding + 100,
            child: IgnorePointer(
              child: Container(
                decoration: BoxDecoration(
                  gradient: LinearGradient(
                    begin: Alignment.topCenter,
                    end: Alignment.bottomCenter,
                    colors: [
                      bgColor,
                      bgColor.withValues(alpha: 0.85),
                      bgColor.withValues(alpha: 0.0),
                    ],
                    stops: const [0.0, 0.6, 1.0],
                  ),
                ),
              ),
            ),
          ),

          // 3. BOTTOM FADE GRADIENT OVERLAY
          Positioned(
            bottom: 0,
            left: 0,
            right: 0,
            height: bottomPadding + 90,
            child: IgnorePointer(
              child: Container(
                decoration: BoxDecoration(
                  gradient: LinearGradient(
                    begin: Alignment.bottomCenter,
                    end: Alignment.topCenter,
                    colors: [
                      bgColor,
                      bgColor.withValues(alpha: 0.85),
                      bgColor.withValues(alpha: 0.0),
                    ],
                    stops: const [0.0, 0.6, 1.0],
                  ),
                ),
              ),
            ),
          ),

          // 4. FLOATING GLASSMORPHIC HEADER BAR
          _GatewaySourcesGlassHeader(
            topPadding: topPadding,
            isDark: isDark,
            onBackTap: () {
              HapticFeedback.selectionClick();
              Navigator.of(context).pop();
            },
            onMarketplaceTap: () {
              HapticFeedback.selectionClick();
              Navigator.of(context).push(
                MaterialPageRoute(builder: (_) => const MCPMarketplaceScreen()),
              );
            },
            onAddCustomTap: () {
              HapticFeedback.selectionClick();
              _showCustomMcpSheet();
            },
            onRefreshTap: () {
              HapticFeedback.selectionClick();
              ref.invalidate(gatewaySourcesProvider);
              ref.invalidate(projectListProvider);
            },
          ),
        ],
      ),
    );
  }

  Future<void> _handleOAuthCallback(Uri uri) async {
    if (uri.scheme != 'riplink' || uri.host != 'oauth' || uri.path != '/callback') return;
    final code = uri.queryParameters['code'];
    final state = uri.queryParameters['state'];
    if (code == null || state == null) {
      setState(() => _statusText = 'Authorization was cancelled.');
      return;
    }
    setState(() => _statusText = 'Completing authorization...');
    try {
      await ref.read(ripClientProvider).completeGatewayOAuth({
        'code': code,
        'state': state,
        'requested_by': 'mobile',
      });
      ref.invalidate(gatewaySourcesProvider);
      setState(() => _statusText = 'Connected. Open GitHub and choose projects.');
    } catch (error) {
      setState(() => _statusText = 'Authorization failed: $error');
    }
  }

  Future<void> _connectOAuth(Map<String, dynamic> source) async {
    final client = ref.read(ripClientProvider);
    final projectId = ref.read(activeProjectIdProvider);
    final sourceId = _sourceId(source);
    final sourceName = _sourceName(source);
    setState(() {
      _busySourceId = sourceId;
      _statusText = null;
    });
    try {
      final configured = await _providerConfigured(client, sourceName);
      if (!configured) {
        if (mounted) setState(() => _busySourceId = null);
        await _useToken(source);
        return;
      }
      final result = await client.reauthorizeGatewaySourceOAuth(sourceId, {
        'redirect_uri': 'riplink://oauth/callback',
        if (projectId != null) 'project_id': projectId,
        'client_type': 'mobile',
        'requested_by': 'mobile',
      });
      final url = Uri.tryParse('${result['authorize_url']}');
      if (url == null) {
        setState(() => _statusText = 'Gateway did not return an authorization URL.');
        return;
      }
      await launchUrl(url, mode: LaunchMode.externalApplication);
      setState(() => _statusText = 'Waiting for GitHub authorization...');
    } catch (_) {
      if (mounted) setState(() => _busySourceId = null);
      await _useToken(source);
      return;
    } finally {
      if (mounted) setState(() => _busySourceId = null);
    }
  }

  Future<bool> _providerConfigured(RipClient client, String providerId) async {
    try {
      final result = await client.gatewayOAuthProviders();
      final providers = (result['providers'] as List? ?? const []).whereType<Map>();
      for (final provider in providers) {
        final item = provider.cast<String, dynamic>();
        if ('${item['id']}' == providerId) {
          return item['configured'] == true;
        }
      }
    } catch (_) {
      return false;
    }
    return false;
  }

  Future<void> _useToken(Map<String, dynamic> source) async {
    final sourceId = _sourceId(source);
    final name = _sourceName(source);
    final controller = TextEditingController();
    final token = await showDialog<String>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text('Connect $name with token'),
        content: TextField(
          controller: controller,
          obscureText: true,
          decoration: const InputDecoration(
            labelText: 'API token',
            helperText: 'Stored encrypted on Gateway. The app never shows it again.',
          ),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.pop(context, controller.text), child: const Text('Connect')),
        ],
      ),
    );
    if (token == null || token.trim().isEmpty) return;
    setState(() {
      _busySourceId = sourceId;
      _statusText = null;
    });
    try {
      await ref.read(ripClientProvider).replaceGatewaySourceCredential(sourceId, token.trim());
      ref.invalidate(gatewaySourcesProvider);
      setState(() => _statusText = '$name connected. Open it and choose projects.');
    } catch (error) {
      setState(() => _statusText = 'Could not save token: $error');
    } finally {
      if (mounted) setState(() => _busySourceId = null);
    }
  }

  Future<void> _disconnect(Map<String, dynamic> source) async {
    final name = _sourceName(source);
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text('Disconnect $name?'),
        content: Text('$name will stop being used in every allocated project.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.pop(context, true), child: const Text('Disconnect')),
        ],
      ),
    );
    if (confirmed != true) return;
    final sourceId = _sourceId(source);
    setState(() => _busySourceId = sourceId);
    try {
      await ref.read(ripClientProvider).revokeGatewaySourceOAuth(sourceId);
      ref.invalidate(gatewaySourcesProvider);
      setState(() => _statusText = '$name disconnected.');
    } finally {
      if (mounted) setState(() => _busySourceId = null);
    }
  }

  Future<void> _showAllocationSheet(Map<String, dynamic> source) async {
    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      builder: (context) => _AllocationSheet(
        client: ref.read(ripClientProvider),
        source: source,
        activeProjectId: ref.read(activeProjectIdProvider),
        onSaved: () {
          ref.invalidate(gatewaySourcesProvider);
          setState(() => _statusText = 'Project allocation saved.');
        },
      ),
    );
  }

  Future<void> _showCustomMcpSheet() async {
    final project = await ref.read(activeProjectProvider.future);
    if (!mounted) return;
    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      builder: (context) => _CustomMcpSheet(
        client: ref.read(ripClientProvider),
        project: project,
        onSaved: () => ref.invalidate(gatewaySourcesProvider),
      ),
    );
  }

  Future<void> _testCustomSource(Map<String, dynamic> source) async {
    final sourceId = _sourceId(source);
    final projectId = ref.read(activeProjectIdProvider);
    setState(() => _busySourceId = sourceId);
    try {
      final result = await ref.read(ripClientProvider).testGatewaySource(sourceId, projectId: projectId);
      setState(() => _statusText = '${_sourceName(source)} test: ${result['status'] ?? 'unknown'}');
      ref.invalidate(gatewaySourcesProvider);
    } finally {
      if (mounted) setState(() => _busySourceId = null);
    }
  }

  void _showAddRepo() {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (context) => const AddRepoSheet(),
    );
  }
}

class _ProjectPanel extends StatelessWidget {
  const _ProjectPanel({
    required this.project,
    required this.onAddRepo,
    required this.isDark,
    required this.cardBgColor,
    required this.textColor,
    required this.mutedTextColor,
  });

  final Project? project;
  final VoidCallback onAddRepo;
  final bool isDark;
  final Color cardBgColor;
  final Color textColor;
  final Color mutedTextColor;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: _panelDecoration(isDark, cardBgColor),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.all(10),
            decoration: BoxDecoration(
              color: isDark ? const Color(0xFF22222E) : AppColors.primary.withValues(alpha: 0.1),
              borderRadius: BorderRadius.circular(12),
            ),
            child: const Icon(Icons.account_tree_rounded, color: AppColors.primary, size: 22),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  project == null ? 'No active project' : project!.projectName,
                  style: TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w600,
                    color: textColor,
                  ),
                ),
                const SizedBox(height: 3),
                Text(
                  project == null
                      ? 'Connect GitHub now, then add a repo when you want project allocation.'
                      : 'Integrations can be allocated to this project after connection.',
                  style: TextStyle(
                    fontSize: 11.5,
                    color: mutedTextColor,
                    height: 1.3,
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(width: 8),
          InkWell(
            onTap: () {
              HapticFeedback.selectionClick();
              onAddRepo();
            },
            borderRadius: BorderRadius.circular(10),
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              decoration: BoxDecoration(
                color: isDark ? const Color(0xFF22222E) : Colors.black.withValues(alpha: 0.05),
                borderRadius: BorderRadius.circular(10),
                border: Border.all(
                  color: isDark ? Colors.white.withValues(alpha: 0.1) : Colors.black.withValues(alpha: 0.08),
                ),
              ),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(Icons.add_rounded, size: 16, color: textColor),
                  const SizedBox(width: 4),
                  Text(
                    'Add repo',
                    style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: textColor),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _IntegrationCard extends StatelessWidget {
  const _IntegrationCard({
    required this.source,
    required this.busy,
    required this.onConnect,
    required this.onUseToken,
    required this.onReconnect,
    required this.onDisconnect,
    required this.onAllocate,
    required this.isDark,
    required this.cardBgColor,
    required this.textColor,
    required this.mutedTextColor,
  });

  final Map<String, dynamic> source;
  final bool busy;
  final VoidCallback onConnect;
  final VoidCallback onUseToken;
  final VoidCallback onReconnect;
  final VoidCallback onDisconnect;
  final VoidCallback onAllocate;
  final bool isDark;
  final Color cardBgColor;
  final Color textColor;
  final Color mutedTextColor;

  @override
  Widget build(BuildContext context) {
    final connected = source['connected'] == true;
    final state = '${source['integration_state'] ?? (connected ? 'connected' : 'not_connected')}';
    final name = _sourceName(source);
    final allocationCount = source['allocation_count'] as int? ?? 0;
    final account = '${source['oauth_account_label'] ?? 'Not connected'}';
    final tools = _sourceTools(source);

    return Container(
      padding: const EdgeInsets.all(14),
      decoration: _panelDecoration(isDark, cardBgColor),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: isDark ? const Color(0xFF22222E) : Colors.black.withValues(alpha: 0.04),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Icon(
                  _sourceIcon(name),
                  color: connected ? const Color(0xFF4ADE80) : AppColors.primary,
                  size: 20,
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      name.toUpperCase(),
                      style: TextStyle(
                        fontSize: 13.5,
                        fontWeight: FontWeight.w700,
                        letterSpacing: 0.5,
                        color: textColor,
                      ),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      connected ? '$account • $allocationCount project(s)' : _stateText(state),
                      style: TextStyle(fontSize: 11.5, color: mutedTextColor),
                    ),
                  ],
                ),
              ),
              if (busy)
                const SizedBox.square(dimension: 20, child: CircularProgressIndicator(strokeWidth: 2, color: AppColors.primary))
              else
                _StateChip(state: state, connected: connected, isDark: isDark),
            ],
          ),
          const SizedBox(height: 12),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              if (!connected) ...[
                _GlassActionButton(
                  icon: Icons.login_rounded,
                  label: 'Connect',
                  isPrimary: true,
                  onPressed: busy ? null : onConnect,
                  isDark: isDark,
                  textColor: textColor,
                ),
                _GlassActionButton(
                  icon: Icons.vpn_key_rounded,
                  label: 'Use Token',
                  isPrimary: false,
                  onPressed: busy ? null : onUseToken,
                  isDark: isDark,
                  textColor: textColor,
                ),
              ] else ...[
                _GlassActionButton(
                  icon: Icons.rule_rounded,
                  label: 'Projects',
                  isPrimary: true,
                  onPressed: busy ? null : onAllocate,
                  isDark: isDark,
                  textColor: textColor,
                ),
                _GlassActionButton(
                  icon: Icons.refresh_rounded,
                  label: 'Reconnect',
                  isPrimary: false,
                  onPressed: busy ? null : onReconnect,
                  isDark: isDark,
                  textColor: textColor,
                ),
                _GlassActionButton(
                  icon: Icons.link_off_rounded,
                  label: 'Disconnect',
                  isPrimary: false,
                  onPressed: busy ? null : onDisconnect,
                  isDark: isDark,
                  textColor: textColor,
                ),
              ],
            ],
          ),
          if (tools.isNotEmpty) ...[
            const SizedBox(height: 12),
            _SourceToolsBlock(tools: tools, isDark: isDark, textColor: textColor, mutedTextColor: mutedTextColor),
          ],
        ],
      ),
    );
  }
}

class _CustomToolsSection extends StatelessWidget {
  const _CustomToolsSection({
    required this.hasProjects,
    required this.sourcesAsync,
    required this.onAdd,
    required this.onReplaceCredential,
    required this.onTest,
    required this.isDark,
    required this.cardBgColor,
    required this.textColor,
    required this.mutedTextColor,
  });

  final bool hasProjects;
  final AsyncValue<Map<String, dynamic>> sourcesAsync;
  final VoidCallback onAdd;
  final void Function(Map<String, dynamic> source) onReplaceCredential;
  final void Function(Map<String, dynamic> source) onTest;
  final bool isDark;
  final Color cardBgColor;
  final Color textColor;
  final Color mutedTextColor;

  @override
  Widget build(BuildContext context) {
    if (!hasProjects) {
      return _EmptyPanel(
        title: 'No project for custom tools',
        message: 'Add repo first. Custom MCP tools are saved under the active project.',
        isDark: isDark,
        cardBgColor: cardBgColor,
        mutedTextColor: mutedTextColor,
      );
    }
    return sourcesAsync.when(
      data: (data) {
        final tools = _orderedSources(data)
            .where((source) => !_isAccountIntegration(source) && source['name'] != 'rip')
            .toList();
        return Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            InkWell(
              onTap: () {
                HapticFeedback.selectionClick();
                onAdd();
              },
              borderRadius: BorderRadius.circular(14),
              child: Container(
                padding: const EdgeInsets.symmetric(vertical: 12, horizontal: 16),
                decoration: BoxDecoration(
                  color: isDark ? const Color(0xFF14141A) : Colors.white,
                  borderRadius: BorderRadius.circular(14),
                  border: Border.all(
                    color: isDark ? Colors.white.withValues(alpha: 0.12) : Colors.black.withValues(alpha: 0.08),
                  ),
                ),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Icon(Icons.add_rounded, size: 18, color: textColor),
                    const SizedBox(width: 8),
                    Text(
                      'Add custom MCP tool',
                      style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: textColor),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 10),
            if (tools.isEmpty)
              _EmptyPanel(
                title: 'No custom tools',
                message: 'Add an MCP endpoint or stdio tool for this project.',
                isDark: isDark,
                cardBgColor: cardBgColor,
                mutedTextColor: mutedTextColor,
              )
            else
              for (final source in tools) ...[
                _CustomToolCard(
                  source: source,
                  onReplaceCredential: () => onReplaceCredential(source),
                  onTest: () => onTest(source),
                  isDark: isDark,
                  cardBgColor: cardBgColor,
                  textColor: textColor,
                  mutedTextColor: mutedTextColor,
                ),
                const SizedBox(height: 10),
              ],
          ],
        );
      },
      loading: () => _LoadingPanel(isDark: isDark, cardBgColor: cardBgColor),
      error: (error, _) => _ErrorPanel(
        message: 'Custom tools unavailable: $error',
        isDark: isDark,
        cardBgColor: cardBgColor,
      ),
    );
  }
}
class _CustomToolCard extends StatelessWidget {
  const _CustomToolCard({
    required this.source,
    required this.onReplaceCredential,
    required this.onTest,
    required this.isDark,
    required this.cardBgColor,
    required this.textColor,
    required this.mutedTextColor,
  });

  final Map<String, dynamic> source;
  final VoidCallback onReplaceCredential;
  final VoidCallback onTest;
  final bool isDark;
  final Color cardBgColor;
  final Color textColor;
  final Color mutedTextColor;

  @override
  Widget build(BuildContext context) {
    final tools = _sourceTools(source);
    final transport = '${source['transport'] ?? 'mcp'}'.toUpperCase();
    final health = '${source['health_status'] ?? 'unknown'}';

    return Container(
      padding: const EdgeInsets.all(14),
      decoration: _panelDecoration(isDark, cardBgColor),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: isDark ? const Color(0xFF22222E) : Colors.black.withValues(alpha: 0.04),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: const Icon(Icons.hub_rounded, color: AppColors.primary, size: 20),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      _sourceName(source).toUpperCase(),
                      style: TextStyle(
                        fontSize: 13.5,
                        fontWeight: FontWeight.w700,
                        letterSpacing: 0.5,
                        color: textColor,
                      ),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      '$transport • $health',
                      style: TextStyle(fontSize: 11.5, color: mutedTextColor),
                    ),
                  ],
                ),
              ),
              InkWell(
                onTap: () {
                  HapticFeedback.selectionClick();
                  onReplaceCredential();
                },
                borderRadius: BorderRadius.circular(8),
                child: Container(
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(
                    color: isDark ? const Color(0xFF22222E) : Colors.black.withValues(alpha: 0.05),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Icon(Icons.vpn_key_rounded, size: 16, color: textColor),
                ),
              ),
              const SizedBox(width: 6),
              InkWell(
                onTap: () {
                  HapticFeedback.selectionClick();
                  onTest();
                },
                borderRadius: BorderRadius.circular(8),
                child: Container(
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(
                    color: isDark ? const Color(0xFF22222E) : Colors.black.withValues(alpha: 0.05),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Icon(Icons.cable_rounded, size: 16, color: textColor),
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          if (tools.isEmpty)
            Text(
              'Tap Test to discover the tools this server actually offers.',
              style: TextStyle(fontSize: 12, color: mutedTextColor, fontStyle: FontStyle.italic),
            )
          else
            _SourceToolsBlock(tools: tools, isDark: isDark, textColor: textColor, mutedTextColor: mutedTextColor),
        ],
      ),
    );
  }
}

class _SourceToolsBlock extends StatelessWidget {
  const _SourceToolsBlock({
    required this.tools,
    required this.isDark,
    required this.textColor,
    required this.mutedTextColor,
  });

  final List<Map<String, dynamic>> tools;
  final bool isDark;
  final Color textColor;
  final Color mutedTextColor;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          'AVAILABLE TOOLS (${tools.length})',
          style: TextStyle(
            fontSize: 10.5,
            fontWeight: FontWeight.w700,
            letterSpacing: 0.8,
            color: mutedTextColor,
          ),
        ),
        const SizedBox(height: 8),
        Wrap(
          spacing: 6,
          runSpacing: 6,
          children: [
            for (final tool in tools) _SourceToolChip(tool: tool, isDark: isDark, textColor: textColor),
          ],
        ),
      ],
    );
  }
}

class _SourceToolChip extends StatelessWidget {
  const _SourceToolChip({
    required this.tool,
    required this.isDark,
    required this.textColor,
  });

  final Map<String, dynamic> tool;
  final bool isDark;
  final Color textColor;

  @override
  Widget build(BuildContext context) {
    final name = '${tool['name'] ?? 'tool'}'.trim();
    final description = '${tool['description'] ?? ''}'.trim();
    return Tooltip(
      message: description.isEmpty ? name : description,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
        decoration: BoxDecoration(
          color: isDark ? const Color(0xFF22222E) : Colors.black.withValues(alpha: 0.05),
          borderRadius: BorderRadius.circular(8),
          border: Border.all(
            color: isDark ? Colors.white.withValues(alpha: 0.06) : Colors.black.withValues(alpha: 0.04),
          ),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              Icons.build_circle_outlined,
              size: 14,
              color: isDark ? Colors.white70 : AppColors.primary,
            ),
            const SizedBox(width: 6),
            ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 160),
              child: Text(
                name.isEmpty ? 'tool' : name,
                style: TextStyle(fontSize: 11.5, fontWeight: FontWeight.w500, color: textColor),
                overflow: TextOverflow.ellipsis,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _AllocationSheet extends StatefulWidget {
  const _AllocationSheet({
    required this.client,
    required this.source,
    required this.activeProjectId,
    required this.onSaved,
  });

  final RipClient client;
  final Map<String, dynamic> source;
  final String? activeProjectId;
  final VoidCallback onSaved;

  @override
  State<_AllocationSheet> createState() => _AllocationSheetState();
}

class _AllocationSheetState extends State<_AllocationSheet> {
  late Future<List<Project>> _projectsFuture;
  late Set<String> _selected;
  bool _busy = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _projectsFuture = widget.client.listProjects();
    _selected = (widget.source['allocated_project_ids'] as List? ?? const [])
        .map((id) => '$id')
        .where((id) => id.isNotEmpty)
        .toSet();
    _loadCurrent();
  }

  Future<void> _loadCurrent() async {
    try {
      final result = await widget.client.gatewayIntegrationProjects(_sourceId(widget.source));
      final ids = (result['project_ids'] as List? ?? const [])
          .map((id) => '$id')
          .where((id) => id.isNotEmpty)
          .toSet();
      if (mounted) setState(() => _selected = ids);
    } catch (_) {
      // Use source-list allocation payload as fallback.
    }
  }

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final cardBgColor = isDark ? const Color(0xFF14141A) : Colors.white;
    final mutedTextColor = isDark ? Colors.white54 : AppColors.textSecondary;

    return SafeArea(
      child: Padding(
        padding: EdgeInsets.only(
          left: 14,
          right: 14,
          top: 14,
          bottom: MediaQuery.of(context).viewInsets.bottom + 14,
        ),
        child: FutureBuilder<List<Project>>(
          future: _projectsFuture,
          builder: (context, snapshot) {
            final projects = snapshot.data ?? const <Project>[];
            return Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Projects for ${_sourceName(widget.source)}', style: Theme.of(context).textTheme.titleLarge),
                const SizedBox(height: 6),
                Text(
                  'Select any number of projects. Leaving all unchecked keeps it connected but unused.',
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(color: AppColors.textSecondary),
                ),
                const SizedBox(height: 12),
                if (snapshot.connectionState == ConnectionState.waiting)
                  const Center(child: CircularProgressIndicator())
                else if (projects.isEmpty)
                  _EmptyPanel(
                    title: 'No projects yet',
                    message: 'Use Add repo in the drawer to create one.',
                    isDark: isDark,
                    cardBgColor: cardBgColor,
                    mutedTextColor: mutedTextColor,
                  )
                else
                  Flexible(
                    child: ListView(
                      shrinkWrap: true,
                      children: [
                        for (final project in projects)
                          CheckboxListTile(
                            value: _selected.contains(project.projectId),
                            onChanged: _busy
                                ? null
                                : (value) {
                                    setState(() {
                                      if (value == true) {
                                        _selected.add(project.projectId);
                                      } else {
                                        _selected.remove(project.projectId);
                                      }
                                    });
                                  },
                            title: Text(
                              project.projectId == widget.activeProjectId
                                  ? '${project.projectName} (active)'
                                  : project.projectName,
                              overflow: TextOverflow.ellipsis,
                            ),
                            subtitle: Text(project.locationLabel, overflow: TextOverflow.ellipsis),
                          ),
                      ],
                    ),
                  ),
                const SizedBox(height: 12),
                Align(
                  alignment: Alignment.centerRight,
                  child: FilledButton.icon(
                    onPressed: _busy ? null : _save,
                    icon: _busy
                        ? const SizedBox.square(
                            dimension: 18,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : const Icon(Icons.save_rounded),
                    label: Text('Save ${_selected.length}'),
                  ),
                ),
                if (_error != null) ...[
                  const SizedBox(height: 10),
                  _StatusBanner(message: _error!, isDark: isDark),
                ],
              ],
            );
          },
        ),
      ),
    );
  }

  Future<void> _save() async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await widget.client.updateGatewayIntegrationProjects(_sourceId(widget.source), _selected.toList());
      widget.onSaved();
      if (mounted) Navigator.pop(context);
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _error =
            'Could not save project allocation. Restart Gateway/server so the source project-allocation route is available, then try again.';
      });
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }
}

class _CustomMcpSheet extends StatefulWidget {
  const _CustomMcpSheet({
    required this.client,
    required this.project,
    required this.onSaved,
  });

  final RipClient client;
  final Project? project;
  final VoidCallback onSaved;

  @override
  State<_CustomMcpSheet> createState() => _CustomMcpSheetState();
}

class _CustomMcpSheetState extends State<_CustomMcpSheet> {
  final _name = TextEditingController();
  final _endpoint = TextEditingController();
  final _credential = TextEditingController();
  final _tool = TextEditingController(text: 'search');
  String _authType = 'bearer';
  bool _busy = false;
  String? _status;

  @override
  void dispose() {
    _name.dispose();
    _endpoint.dispose();
    _credential.dispose();
    _tool.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final cardBgColor = isDark ? const Color(0xFF14141A) : Colors.white;
    final mutedTextColor = isDark ? Colors.white54 : AppColors.textSecondary;

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
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('Add custom MCP tool', style: Theme.of(context).textTheme.titleLarge),
              const SizedBox(height: 8),
              if (widget.project == null)
                _EmptyPanel(
                  title: 'Select a project first',
                  message: 'Custom MCP tools are stored under the active project. Use Add repo if you have none.',
                  isDark: isDark,
                  cardBgColor: cardBgColor,
                  mutedTextColor: mutedTextColor,
                )
              else ...[
                TextField(controller: _name, decoration: const InputDecoration(labelText: 'Name')),
                const SizedBox(height: 10),
                TextField(controller: _endpoint, decoration: const InputDecoration(labelText: 'MCP endpoint URL')),
                const SizedBox(height: 10),
                DropdownButtonFormField<String>(
                  initialValue: _authType,
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
                TextField(controller: _tool, decoration: const InputDecoration(labelText: 'Tool name')),
                const SizedBox(height: 14),
                Align(
                  alignment: Alignment.centerRight,
                  child: FilledButton.icon(
                    onPressed: _busy ? null : _save,
                    icon: _busy
                        ? const SizedBox.square(
                            dimension: 18,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : const Icon(Icons.save_rounded),
                    label: const Text('Save'),
                  ),
                ),
                if (_status != null) ...[
                  const SizedBox(height: 10),
                  _StatusBanner(message: _status!, isDark: isDark),
                ],
              ],
            ],
          ),
        ),
      ),
    );
  }

  Future<void> _save() async {
    if (_name.text.trim().isEmpty || _endpoint.text.trim().isEmpty || widget.project == null) return;
    setState(() => _busy = true);
    try {
      await widget.client.createGatewaySource({
        'name': _name.text.trim(),
        'project_id': widget.project!.projectId,
        'kind': 'mcp',
        'transport': 'streamable_http',
        'endpoint_url': _endpoint.text.trim(),
        'auth_type': _authType,
        if (_credential.text.trim().isNotEmpty) 'credential': _credential.text.trim(),
        'tool_name': _tool.text.trim().isEmpty ? 'search' : _tool.text.trim(),
        'domain_hints': ['custom'],
        'priority_hint': 50,
        'enabled': true,
      });
      widget.onSaved();
      if (mounted) Navigator.pop(context);
    } catch (error) {
      setState(() => _status = 'Could not save: $error');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }
}

class _StatusBanner extends StatelessWidget {
  const _StatusBanner({required this.message, required this.isDark});

  final String message;
  final bool isDark;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppColors.primary.withValues(alpha: isDark ? 0.12 : 0.08),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppColors.primary.withValues(alpha: 0.25)),
      ),
      child: Text(
        message,
        style: TextStyle(fontSize: 12, color: isDark ? Colors.white70 : AppColors.textSecondary),
      ),
    );
  }
}

class _LoadingPanel extends StatelessWidget {
  const _LoadingPanel({required this.isDark, required this.cardBgColor});

  final bool isDark;
  final Color cardBgColor;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(28),
      decoration: _panelDecoration(isDark, cardBgColor),
      child: const Center(child: CircularProgressIndicator(strokeWidth: 2, color: AppColors.primary)),
    );
  }
}

class _ErrorPanel extends StatelessWidget {
  const _ErrorPanel({required this.message, required this.isDark, required this.cardBgColor});

  final String message;
  final bool isDark;
  final Color cardBgColor;

  @override
  Widget build(BuildContext context) {
    return _EmptyPanel(
      title: 'Unavailable',
      message: message,
      isDark: isDark,
      cardBgColor: cardBgColor,
      mutedTextColor: Colors.redAccent,
    );
  }
}

class _EmptyPanel extends StatelessWidget {
  const _EmptyPanel({
    required this.title,
    required this.message,
    required this.isDark,
    required this.cardBgColor,
    required this.mutedTextColor,
  });

  final String title;
  final String message;
  final bool isDark;
  final Color cardBgColor;
  final Color mutedTextColor;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(16),
      decoration: _panelDecoration(isDark, cardBgColor),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            title,
            style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: isDark ? Colors.white : Colors.black87),
          ),
          const SizedBox(height: 4),
          Text(message, style: TextStyle(fontSize: 12, color: mutedTextColor)),
        ],
      ),
    );
  }
}

class _GlassActionButton extends StatelessWidget {
  const _GlassActionButton({
    required this.icon,
    required this.label,
    required this.isPrimary,
    required this.onPressed,
    required this.isDark,
    required this.textColor,
  });

  final IconData icon;
  final String label;
  final bool isPrimary;
  final VoidCallback? onPressed;
  final bool isDark;
  final Color textColor;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onPressed != null
          ? () {
              HapticFeedback.selectionClick();
              onPressed!();
            }
          : null,
      borderRadius: BorderRadius.circular(10),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 7),
        decoration: BoxDecoration(
          color: isPrimary
              ? (isDark ? const Color(0xFF22222E) : Colors.black.withValues(alpha: 0.06))
              : Colors.transparent,
          borderRadius: BorderRadius.circular(10),
          border: Border.all(
            color: isDark ? Colors.white.withValues(alpha: 0.1) : Colors.black.withValues(alpha: 0.08),
          ),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 14, color: isPrimary ? AppColors.primary : textColor),
            const SizedBox(width: 6),
            Text(
              label,
              style: TextStyle(
                fontSize: 12,
                fontWeight: isPrimary ? FontWeight.w600 : FontWeight.w500,
                color: textColor,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _StateChip extends StatelessWidget {
  const _StateChip({
    required this.state,
    required this.connected,
    required this.isDark,
  });

  final String state;
  final bool connected;
  final bool isDark;

  @override
  Widget build(BuildContext context) {
    final color = connected ? const Color(0xFF4ADE80) : AppColors.primary;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: color.withValues(alpha: isDark ? 0.15 : 0.1),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: color.withValues(alpha: 0.3)),
      ),
      child: Text(
        connected ? 'ACTIVE' : 'DISCONNECTED',
        style: TextStyle(
          fontSize: 10,
          fontWeight: FontWeight.w700,
          letterSpacing: 0.6,
          color: color,
        ),
      ),
    );
  }
}

class _SectionLabel extends StatelessWidget {
  const _SectionLabel({
    required this.title,
    required this.icon,
    required this.isDark,
  });

  final String title;
  final IconData icon;
  final bool isDark;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Icon(icon, size: 14, color: isDark ? Colors.white54 : AppColors.textSecondary),
        const SizedBox(width: 6),
        Text(
          title,
          style: TextStyle(
            fontSize: 11,
            fontWeight: FontWeight.w700,
            letterSpacing: 0.8,
            color: isDark ? Colors.white54 : AppColors.textSecondary,
          ),
        ),
      ],
    );
  }
}

class _GatewaySourcesGlassHeader extends StatelessWidget {
  const _GatewaySourcesGlassHeader({
    required this.topPadding,
    required this.isDark,
    required this.onBackTap,
    required this.onMarketplaceTap,
    required this.onAddCustomTap,
    required this.onRefreshTap,
  });

  final double topPadding;
  final bool isDark;
  final VoidCallback onBackTap;
  final VoidCallback onMarketplaceTap;
  final VoidCallback onAddCustomTap;
  final VoidCallback onRefreshTap;

  @override
  Widget build(BuildContext context) {
    return Positioned(
      top: topPadding + 8,
      left: 16,
      right: 16,
      child: Row(
        children: [
          // 1. BACK ARROW GLASS PILL
          Container(
            width: 44,
            height: 44,
            decoration: BoxDecoration(
              color: isDark
                  ? const Color(0xFF14141A).withValues(alpha: 0.8)
                  : Colors.white.withValues(alpha: 0.85),
              shape: BoxShape.circle,
              border: Border.all(
                color: isDark ? Colors.white.withValues(alpha: 0.12) : Colors.black.withValues(alpha: 0.08),
              ),
              boxShadow: [
                BoxShadow(
                  color: Colors.black.withValues(alpha: isDark ? 0.3 : 0.08),
                  blurRadius: 16,
                  offset: const Offset(0, 4),
                ),
              ],
            ),
            child: Material(
              color: Colors.transparent,
              child: InkWell(
                onTap: onBackTap,
                customBorder: const CircleBorder(),
                child: Icon(
                  Icons.arrow_back_rounded,
                  size: 20,
                  color: isDark ? Colors.white : AppColors.textPrimary,
                ),
              ),
            ),
          ),
          const SizedBox(width: 8),

          // 2. TITLE GLASS PILL
          Expanded(
            child: Container(
              height: 44,
              padding: const EdgeInsets.symmetric(horizontal: 14),
              decoration: BoxDecoration(
                color: isDark
                    ? const Color(0xFF14141A).withValues(alpha: 0.8)
                    : Colors.white.withValues(alpha: 0.85),
                borderRadius: BorderRadius.circular(22),
                border: Border.all(
                  color: isDark ? Colors.white.withValues(alpha: 0.12) : Colors.black.withValues(alpha: 0.08),
                ),
                boxShadow: [
                  BoxShadow(
                    color: Colors.black.withValues(alpha: isDark ? 0.3 : 0.08),
                    blurRadius: 16,
                    offset: const Offset(0, 4),
                  ),
                ],
              ),
              child: Row(
                children: [
                  Icon(
                    Icons.hub_rounded,
                    size: 18,
                    color: isDark ? Colors.white70 : AppColors.textPrimary,
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      'Gateway Sources',
                      style: TextStyle(
                        fontSize: 14,
                        fontWeight: FontWeight.w600,
                        color: isDark ? Colors.white : AppColors.textPrimary,
                      ),
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(width: 8),

          // 3. MCP MARKETPLACE GLASS PILL
          Container(
            width: 44,
            height: 44,
            decoration: BoxDecoration(
              color: isDark
                  ? const Color(0xFF14141A).withValues(alpha: 0.8)
                  : Colors.white.withValues(alpha: 0.85),
              shape: BoxShape.circle,
              border: Border.all(
                color: isDark ? Colors.white.withValues(alpha: 0.12) : Colors.black.withValues(alpha: 0.08),
              ),
              boxShadow: [
                BoxShadow(
                  color: Colors.black.withValues(alpha: isDark ? 0.3 : 0.08),
                  blurRadius: 16,
                  offset: const Offset(0, 4),
                ),
              ],
            ),
            child: Material(
              color: Colors.transparent,
              child: InkWell(
                onTap: onMarketplaceTap,
                customBorder: const CircleBorder(),
                child: const Icon(
                  Icons.storefront_rounded,
                  size: 20,
                  color: AppColors.primary,
                ),
              ),
            ),
          ),
          const SizedBox(width: 6),

          // 4. ADD CUSTOM MCP GLASS PILL
          Container(
            width: 44,
            height: 44,
            decoration: BoxDecoration(
              color: isDark
                  ? const Color(0xFF14141A).withValues(alpha: 0.8)
                  : Colors.white.withValues(alpha: 0.85),
              shape: BoxShape.circle,
              border: Border.all(
                color: isDark ? Colors.white.withValues(alpha: 0.12) : Colors.black.withValues(alpha: 0.08),
              ),
              boxShadow: [
                BoxShadow(
                  color: Colors.black.withValues(alpha: isDark ? 0.3 : 0.08),
                  blurRadius: 16,
                  offset: const Offset(0, 4),
                ),
              ],
            ),
            child: Material(
              color: Colors.transparent,
              child: InkWell(
                onTap: onAddCustomTap,
                customBorder: const CircleBorder(),
                child: Icon(
                  Icons.add_rounded,
                  size: 20,
                  color: isDark ? Colors.white : AppColors.textPrimary,
                ),
              ),
            ),
          ),
          const SizedBox(width: 6),

          // 5. REFRESH GLASS PILL
          Container(
            width: 44,
            height: 44,
            decoration: BoxDecoration(
              color: isDark
                  ? const Color(0xFF14141A).withValues(alpha: 0.8)
                  : Colors.white.withValues(alpha: 0.85),
              shape: BoxShape.circle,
              border: Border.all(
                color: isDark ? Colors.white.withValues(alpha: 0.12) : Colors.black.withValues(alpha: 0.08),
              ),
              boxShadow: [
                BoxShadow(
                  color: Colors.black.withValues(alpha: isDark ? 0.3 : 0.08),
                  blurRadius: 16,
                  offset: const Offset(0, 4),
                ),
              ],
            ),
            child: Material(
              color: Colors.transparent,
              child: InkWell(
                onTap: onRefreshTap,
                customBorder: const CircleBorder(),
                child: Icon(
                  Icons.refresh_rounded,
                  size: 18,
                  color: isDark ? Colors.white : AppColors.textPrimary,
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

List<Map<String, dynamic>> _orderedSources(Map<String, dynamic> data) {
  final sources = (data['sources'] as List? ?? const [])
      .whereType<Map>()
      .map((item) => item.cast<String, dynamic>())
      .toList();
  const order = {'github': 0, 'jira': 1, 'slack': 2, 'rip': 98};
  sources.sort((a, b) {
    final left = order[_sourceName(a)] ?? 50;
    final right = order[_sourceName(b)] ?? 50;
    if (left != right) return left.compareTo(right);
    return _sourceName(a).compareTo(_sourceName(b));
  });
  return sources;
}

bool _isAccountIntegration(Map<String, dynamic> source) {
  return {'github', 'jira', 'slack'}.contains(_sourceName(source)) || source['auth_type'] == 'oauth2';
}

String _sourceName(Map<String, dynamic> source) {
  return '${source['name'] ?? 'source'}';
}

String _sourceId(Map<String, dynamic> source) {
  return '${source['id'] ?? source['name']}';
}

List<Map<String, dynamic>> _sourceTools(Map<String, dynamic> source) {
  final mcpConfig = source['mcp_config'];
  final capabilities = source['capabilities'] ?? (mcpConfig is Map ? mcpConfig['capabilities'] : null);
  if (capabilities is Map) {
    final tools = capabilities['tools'];
    if (tools is List) {
      final discovered = tools
          .whereType<Map>()
          .map((tool) => Map<String, dynamic>.from(tool))
          .where((tool) => '${tool['name'] ?? ''}'.trim().isNotEmpty)
          .toList();
      if (discovered.isNotEmpty) return discovered;
    }
  }

  final name = _sourceName(source);
  final kind = '${source['kind'] ?? ''}';
  if (kind != 'builtin' && !{'github', 'jira', 'slack', 'rip'}.contains(name)) {
    return const [];
  }

  final toolName = '${source['tool_name'] ?? (mcpConfig is Map ? mcpConfig['tool_name'] : '')}'.trim();
  if (toolName.isEmpty) return const [];
  return [
    {
      'name': toolName,
      'description': 'Configured Gateway tool for $name.',
    },
  ];
}

String _stateText(String state) {
  switch (state) {
    case 'connected_unallocated':
      return 'Connected, but not assigned to a project yet';
    case 'needs_reauth':
      return 'Needs reconnect';
    case 'server_setup_required':
      return 'OAuth setup missing. Use token or ask server admin.';
    case 'manual_intervention_required':
      return 'Token required';
    default:
      return 'Not connected';
  }
}

IconData _sourceIcon(String name) {
  switch (name) {
    case 'github':
      return Icons.code_rounded;
    case 'jira':
      return Icons.assignment_rounded;
    case 'slack':
      return Icons.chat_bubble_outline_rounded;
    default:
      return Icons.hub_rounded;
  }
}

BoxDecoration _panelDecoration(bool isDark, Color cardBgColor) {
  return BoxDecoration(
    color: cardBgColor,
    borderRadius: BorderRadius.circular(16),
    border: Border.all(
      color: isDark ? Colors.white.withValues(alpha: 0.08) : Colors.black.withValues(alpha: 0.06),
    ),
    boxShadow: [
      BoxShadow(
        color: Colors.black.withValues(alpha: isDark ? 0.25 : 0.04),
        blurRadius: 12,
        offset: const Offset(0, 4),
      ),
    ],
  );
}
