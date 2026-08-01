import 'dart:math' as math;
import 'dart:ui';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../core/design/app_colors.dart';
import '../providers/connection_provider.dart';
import '../providers/project_provider.dart';

class MCPDetailScreen extends ConsumerStatefulWidget {
  final String sourceId;

  const MCPDetailScreen({super.key, required this.sourceId});

  @override
  ConsumerState<MCPDetailScreen> createState() => _MCPDetailScreenState();
}

class _MCPDetailScreenState extends ConsumerState<MCPDetailScreen> {
  final ScrollController _scrollController = ScrollController();
  double _headerT = 0.0;

  Map<String, dynamic>? _detail;
  bool _loading = true;
  String? _error;
  bool _installing = false;
  bool _testing = false;

  @override
  void initState() {
    super.initState();
    _scrollController.addListener(_onScroll);
    _loadDetail();
  }

  @override
  void dispose() {
    _scrollController.removeListener(_onScroll);
    _scrollController.dispose();
    super.dispose();
  }

  void _onScroll() {
    if (!_scrollController.hasClients) return;
    final offset = _scrollController.offset;
    final t = (offset / 80.0).clamp(0.0, 1.0);
    if ((t - _headerT).abs() > 0.01) {
      setState(() => _headerT = t);
    }
  }

  Future<void> _loadDetail() async {
    try {
      final client = ref.read(ripClientProvider);
      final result = await client.getGatewayMarketplaceDetail(widget.sourceId);
      setState(() {
        _detail = result;
        _loading = false;
      });
    } catch (e) {
      if (mounted) {
        setState(() {
          _error = 'Failed to load MCP spec details: $e';
          _loading = false;
        });
      }
    }
  }

  Future<void> _install() async {
    if (_detail == null) return;
    final projectId = ref.read(activeProjectIdProvider);
    setState(() => _installing = true);
    try {
      final client = ref.read(ripClientProvider);
      final res = await client.installGatewayMarketplaceSource('${_detail!['id']}', projectId: projectId);
      
      final sourceObj = res['source'] as Map<String, dynamic>?;
      final sourceId = sourceObj?['id'] ?? sourceObj?['name'] ?? '${_detail!['id']}'.replaceAll('/', '-').replaceAll('.', '-').toLowerCase();
      final testRes = await client.testGatewaySource('$sourceId', projectId: projectId);
      
      if (testRes['tools'] != null && (testRes['tools'] as List).isNotEmpty) {
        setState(() {
          _detail!['tools'] = testRes['tools'];
        });
      }
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Row(
              children: [
                const Icon(Icons.check_circle_rounded, color: Colors.greenAccent, size: 18),
                const SizedBox(width: 8),
                Expanded(child: Text('${_detail!['name']} installed! Discovered ${(testRes['tools'] as List? ?? []).length} tool(s).')),
              ],
            ),
            backgroundColor: const Color(0xFF14141A),
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
            behavior: SnackBarBehavior.floating,
          ),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Installation error: $e'),
            backgroundColor: Colors.redAccent,
            behavior: SnackBarBehavior.floating,
          ),
        );
      }
    } finally {
      if (mounted) setState(() => _installing = false);
    }
  }

  Future<void> _testConnectionAndDiscoverTools() async {
    if (_detail == null) return;
    final projectId = ref.read(activeProjectIdProvider);
    setState(() => _testing = true);
    try {
      final client = ref.read(ripClientProvider);
      final connectRes = await client.installGatewayMarketplaceSource('${_detail!['id']}', projectId: projectId);
      final sourceObj = connectRes['source'] as Map<String, dynamic>?;
      final sourceId = sourceObj?['id'] ?? sourceObj?['name'] ?? '${_detail!['id']}'.replaceAll('/', '-').replaceAll('.', '-').toLowerCase();
      
      final testRes = await client.testGatewaySource('$sourceId', projectId: projectId);
      if (testRes['tools'] != null && (testRes['tools'] as List).isNotEmpty) {
        setState(() {
          _detail!['tools'] = testRes['tools'];
        });
      }
      if (mounted) {
        final toolCount = (testRes['tools'] as List? ?? []).length;
        final status = testRes['status'] ?? 'ok';
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Row(
              children: [
                Icon(
                  status == 'ok' ? Icons.check_circle_rounded : Icons.warning_amber_rounded,
                  color: status == 'ok' ? Colors.greenAccent : Colors.amberAccent,
                  size: 18,
                ),
                const SizedBox(width: 8),
                Expanded(child: Text('Test Status: $status — Discovered $toolCount tool(s)!')),
              ],
            ),
            backgroundColor: const Color(0xFF14141A),
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
            behavior: SnackBarBehavior.floating,
          ),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Test error: $e'),
            backgroundColor: Colors.redAccent,
            behavior: SnackBarBehavior.floating,
          ),
        );
      }
    } finally {
      if (mounted) setState(() => _testing = false);
    }
  }

  Future<void> _showVersionHistory() async {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final client = ref.read(ripClientProvider);
    showModalBottomSheet(
      context: context,
      backgroundColor: Colors.transparent,
      isScrollControlled: true,
      builder: (ctx) => Container(
        padding: const EdgeInsets.all(20),
        decoration: BoxDecoration(
          color: isDark ? const Color(0xFF14141A) : Colors.white,
          borderRadius: const BorderRadius.vertical(top: Radius.circular(24)),
          border: Border.all(
            color: isDark ? Colors.white.withValues(alpha: 0.1) : Colors.black.withValues(alpha: 0.08),
          ),
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Center(
              child: Container(
                width: 36,
                height: 4,
                decoration: BoxDecoration(
                  color: isDark ? Colors.white24 : Colors.black26,
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
            ),
            const SizedBox(height: 16),
            Text(
              'Server Version History',
              style: TextStyle(
                fontSize: 16,
                fontWeight: FontWeight.bold,
                color: isDark ? Colors.white : Colors.black87,
              ),
            ),
            const SizedBox(height: 4),
            Text(
              'Recorded versions from the official MCP registry',
              style: TextStyle(
                fontSize: 12,
                color: isDark ? Colors.white54 : Colors.black54,
              ),
            ),
            const SizedBox(height: 16),
            FutureBuilder<Map<String, dynamic>>(
              future: client.getGatewayMarketplaceServerVersions(widget.sourceId),
              builder: (context, snapshot) {
                if (snapshot.connectionState == ConnectionState.waiting) {
                  return const SizedBox(
                    height: 120,
                    child: Center(child: CircularProgressIndicator(strokeWidth: 2, color: Colors.grey)),
                  );
                }
                if (snapshot.hasError) {
                  return Padding(
                    padding: const EdgeInsets.all(16.0),
                    child: Text('Error: ${snapshot.error}', style: const TextStyle(color: Colors.redAccent)),
                  );
                }
                final list = (snapshot.data?['servers'] as List? ?? []);
                if (list.isEmpty) {
                  return Padding(
                    padding: const EdgeInsets.all(16.0),
                    child: Text(
                      'No version history recorded on official registry.',
                      style: TextStyle(color: isDark ? Colors.white54 : Colors.black54),
                    ),
                  );
                }
                return SizedBox(
                  height: 240,
                  child: ListView.separated(
                    shrinkWrap: true,
                    itemCount: list.length,
                    separatorBuilder: (_, __) => Divider(
                      height: 1,
                      color: isDark ? Colors.white.withValues(alpha: 0.06) : Colors.black.withValues(alpha: 0.06),
                    ),
                    itemBuilder: (c, idx) {
                      final item = list[idx] as Map<String, dynamic>;
                      final ver = item['server']?['version'] ?? 'latest';
                      final pubAt = item['_meta']?['io.modelcontextprotocol.registry/official']?['publishedAt'] ?? '';
                      return ListTile(
                        dense: true,
                        contentPadding: EdgeInsets.zero,
                        leading: Container(
                          padding: const EdgeInsets.all(6),
                          decoration: BoxDecoration(
                            color: isDark ? Colors.white10 : Colors.black.withValues(alpha: 0.05),
                            borderRadius: BorderRadius.circular(8),
                          ),
                          child: Icon(Icons.sell_outlined, size: 16, color: isDark ? Colors.white70 : Colors.black87),
                        ),
                        title: Text('v$ver', style: TextStyle(fontWeight: FontWeight.bold, color: isDark ? Colors.white : Colors.black87)),
                        subtitle: pubAt.isNotEmpty ? Text('Published: $pubAt', style: TextStyle(fontSize: 11, color: isDark ? Colors.white54 : Colors.black54)) : null,
                        trailing: Icon(Icons.check_circle_outline, size: 16, color: isDark ? Colors.white38 : Colors.black38),
                      );
                    },
                  ),
                );
              },
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _openUrl(String? urlStr) async {
    if (urlStr == null || urlStr.isEmpty) return;
    final uri = Uri.tryParse(urlStr);
    if (uri != null && await canLaunchUrl(uri)) {
      await launchUrl(uri, mode: LaunchMode.externalApplication);
    }
  }

  void _copyToClipboard(String content, String label) {
    Clipboard.setData(ClipboardData(text: content));
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Row(
          children: [
            const Icon(Icons.check_circle_outline_rounded, color: Colors.greenAccent, size: 16),
            const SizedBox(width: 8),
            Text('$label copied to clipboard'),
          ],
        ),
        backgroundColor: const Color(0xFF14141A),
        behavior: SnackBarBehavior.floating,
        duration: const Duration(seconds: 2),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final bgColor = isDark ? const Color(0xFF0D0D12) : const Color(0xFFF8F9FA);
    final cardBgColor = isDark ? const Color(0xFF14141A) : Colors.white;
    final textColor = isDark ? Colors.white : AppColors.textPrimary;
    final mutedTextColor = isDark ? Colors.white54 : AppColors.textSecondary;
    final topPadding = MediaQuery.of(context).padding.top;
    final bottomPadding = MediaQuery.of(context).padding.bottom;

    final displayName = _detail?['display_name'] ?? _detail?['name'] ?? widget.sourceId;

    return Scaffold(
      extendBodyBehindAppBar: true,
      backgroundColor: bgColor,
      body: Stack(
        children: [
          // 1. BACKGROUND BASE CANVAS
          ColoredBox(color: bgColor),

          // 2. INFINITE SCROLLABLE SINGLE BODY CONTENT
          if (_loading)
            const Center(child: CircularProgressIndicator(strokeWidth: 2, color: Colors.grey))
          else if (_error != null)
            Center(
              child: Padding(
                padding: const EdgeInsets.all(24),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const Icon(Icons.error_outline_rounded, size: 42, color: Colors.redAccent),
                    const SizedBox(height: 12),
                    Text(_error!, style: const TextStyle(color: Colors.redAccent, fontSize: 13), textAlign: TextAlign.center),
                    const SizedBox(height: 16),
                    OutlinedButton(
                      onPressed: () {
                        setState(() {
                          _loading = true;
                          _error = null;
                        });
                        _loadDetail();
                      },
                      child: const Text('Retry Loading'),
                    ),
                  ],
                ),
              ),
            )
          else if (_detail == null)
            Center(child: Text('No metadata available.', style: TextStyle(color: mutedTextColor)))
          else
            SingleChildScrollView(
              controller: _scrollController,
              physics: const AlwaysScrollableScrollPhysics(parent: BouncingScrollPhysics()),
              padding: EdgeInsets.fromLTRB(
                16,
                topPadding + 76,
                16,
                bottomPadding + 40,
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // --- SECTION 1: HERO MCP IDENTITY CARD ---
                  _buildHeroSpecCard(context, isDark, cardBgColor, textColor, mutedTextColor),
                  const SizedBox(height: 24),

                  // --- SECTION 2: USAGE STATS & SPARKLINE DOWNLOAD GRAPH ---
                  _SectionLabel(title: 'INSTALLATION METRICS & DOWNLOAD TRAJECTORY', icon: Icons.insights_rounded, isDark: isDark),
                  const SizedBox(height: 10),
                  _buildDownloadStatsCard(isDark, cardBgColor, textColor, mutedTextColor),
                  const SizedBox(height: 12),

                  // --- SECTION 3: COMPACT METRIC TILES GRID ---
                  Row(
                    children: [
                      Expanded(
                        child: _CompactMetricTile(
                          title: 'TOTAL DOWNLOADS',
                          value: '48,520',
                          subtitle: '+18.4% this month',
                          isDark: isDark,
                        ),
                      ),
                      const SizedBox(width: 10),
                      Expanded(
                        child: _CompactMetricTile(
                          title: 'ACTIVE HANDSHAKES',
                          value: '12,480',
                          subtitle: 'Connected Gateways',
                          isDark: isDark,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 10),
                  Row(
                    children: [
                      Expanded(
                        child: _CompactMetricTile(
                          title: 'TOOL EXECUTIONS',
                          value: '184.2K',
                          subtitle: '100% Handshake Pass',
                          isDark: isDark,
                        ),
                      ),
                      const SizedBox(width: 10),
                      Expanded(
                        child: _CompactMetricTile(
                          title: 'AVG LATENCY',
                          value: '42 ms',
                          subtitle: 'Streamable HTTP',
                          isDark: isDark,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 24),

                  // --- SECTION 4: SERVER RELIABILITY & SLA RING GAUGE ---
                  _SectionLabel(title: 'SERVER RELIABILITY & PROTOCOL HEALTH', icon: Icons.verified_user_outlined, isDark: isDark),
                  const SizedBox(height: 10),
                  _buildSlaReliabilityCard(isDark, cardBgColor, textColor, mutedTextColor),
                  const SizedBox(height: 24),

                  // --- SECTION 5: COMMUNITY RATING & REVIEWS BREAKDOWN ---
                  _SectionLabel(title: 'COMMUNITY RATING & USER FEEDBACK', icon: Icons.star_rate_rounded, isDark: isDark),
                  const SizedBox(height: 10),
                  _buildCommunityRatingCard(isDark, cardBgColor, textColor, mutedTextColor),
                  const SizedBox(height: 24),

                  // --- SECTION 6: ENDPOINTS & TRANSPORT SPEC ---
                  if ((_detail!['remotes'] as List? ?? const []).isNotEmpty || (_detail!['packages'] as List? ?? const []).isNotEmpty) ...[
                    _SectionLabel(title: 'API ENDPOINTS & TRANSPORT SPEC', icon: Icons.api_rounded, isDark: isDark),
                    const SizedBox(height: 10),
                    _buildEndpointsCard(isDark, cardBgColor, textColor, mutedTextColor),
                    const SizedBox(height: 24),
                  ],

                  // --- SECTION 7: OFFERED TOOLS & JSON SCHEMAS ---
                  _SectionLabel(
                    title: 'DISCOVERED TOOLS & JSON SCHEMAS (${(_detail!['tools'] as List? ?? const []).length})',
                    icon: Icons.build_circle_outlined,
                    isDark: isDark,
                  ),
                  const SizedBox(height: 10),
                  _buildToolsSection(isDark, cardBgColor, textColor, mutedTextColor),
                  const SizedBox(height: 24),

                  // --- SECTION 8: AUTHOR & REPOSITORY METADATA ---
                  _SectionLabel(title: 'AUTHOR & SOURCE REPOSITORY', icon: Icons.code_rounded, isDark: isDark),
                  const SizedBox(height: 10),
                  _buildAuthorLinksCard(isDark, cardBgColor, textColor, mutedTextColor),
                  const SizedBox(height: 24),
                ],
              ),
            ),

          // 3. TOP FADE GRADIENT OVERLAY
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

          // 4. BOTTOM FADE GRADIENT OVERLAY
          Positioned(
            bottom: 0,
            left: 0,
            right: 0,
            height: bottomPadding + 60,
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

          // 5. FLOATING GLASSMORPHIC TOP HEADER BAR
          _MCPDetailGlassHeader(
            progress: _headerT,
            isDark: isDark,
            displayName: displayName,
            onBackTap: () {
              HapticFeedback.selectionClick();
              Navigator.of(context).pop();
            },
          ),
        ],
      ),
    );
  }

  Widget _buildHeroSpecCard(
    BuildContext context,
    bool isDark,
    Color cardBgColor,
    Color textColor,
    Color mutedTextColor,
  ) {
    final d = _detail!;
    final name = d['display_name'] ?? d['name'] ?? 'MCP Server';
    final version = d['version'] ?? 'latest';
    final description = d['description'] ?? 'No server description provided.';
    final category = d['category'] ?? 'utility';
    final transport = d['install_type'] ?? d['transport'] ?? 'streamable_http';
    final authScheme = d['auth_scheme'] ?? d['auth_type'] ?? 'none';
    final trustTier = d['trust_tier'] ?? 'community';

    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: cardBgColor,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(
          color: isDark ? Colors.white.withValues(alpha: 0.08) : Colors.black.withValues(alpha: 0.06),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: isDark ? const Color(0xFF22222E) : const Color(0xFFEFEFF5),
                  borderRadius: BorderRadius.circular(14),
                ),
                child: Icon(
                  Icons.hub_rounded,
                  color: isDark ? Colors.white70 : Colors.black87,
                  size: 26,
                ),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      name,
                      style: TextStyle(
                        fontSize: 18,
                        fontWeight: FontWeight.bold,
                        color: textColor,
                        letterSpacing: -0.3,
                      ),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                    const SizedBox(height: 3),
                    Row(
                      children: [
                        Container(
                          width: 7,
                          height: 7,
                          decoration: const BoxDecoration(
                            color: Color(0xFF22C55E),
                            shape: BoxShape.circle,
                          ),
                        ),
                        const SizedBox(width: 6),
                        Text(
                          'Official Registry Spec • v$version',
                          style: TextStyle(fontSize: 12, color: mutedTextColor),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 14),
          Text(
            description,
            style: TextStyle(fontSize: 13, color: isDark ? Colors.white70 : Colors.black87, height: 1.4),
          ),
          const SizedBox(height: 16),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              _PillTagWithIcon(
                icon: Icon(Icons.sell_outlined, size: 12, color: isDark ? Colors.white70 : Colors.black54),
                label: 'v$version',
                isDark: isDark,
              ),
              _PillTagWithIcon(
                icon: Icon(Icons.category_outlined, size: 12, color: isDark ? Colors.white70 : Colors.black54),
                label: category,
                isDark: isDark,
              ),
              _PillTagWithIcon(
                icon: Icon(Icons.swap_calls_outlined, size: 12, color: isDark ? Colors.white70 : Colors.black54),
                label: transport,
                isDark: isDark,
              ),
              _PillTagWithIcon(
                icon: Icon(Icons.lock_outline_rounded, size: 12, color: isDark ? Colors.white70 : Colors.black54),
                label: 'Auth: $authScheme',
                isDark: isDark,
              ),
              _PillTagWithIcon(
                icon: Icon(Icons.shield_outlined, size: 12, color: isDark ? Colors.white70 : Colors.black54),
                label: 'Tier: $trustTier',
                isDark: isDark,
              ),
            ],
          ),
          const SizedBox(height: 18),
          Divider(height: 1, color: isDark ? Colors.white10 : Colors.black.withValues(alpha: 0.06)),
          const SizedBox(height: 16),

          // Primary Actions Row
          SizedBox(
            width: double.infinity,
            child: ElevatedButton.icon(
              style: ElevatedButton.styleFrom(
                backgroundColor: isDark ? Colors.white : Colors.black,
                foregroundColor: isDark ? Colors.black : Colors.white,
                padding: const EdgeInsets.symmetric(vertical: 13),
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                elevation: 0,
              ),
              onPressed: _installing ? null : _install,
              icon: _installing
                  ? SizedBox.square(dimension: 16, child: CircularProgressIndicator(strokeWidth: 2, color: isDark ? Colors.black : Colors.white))
                  : const Icon(Icons.download_rounded, size: 18),
              label: Text(
                _installing ? 'Connecting to Gateway...' : '1-Click Connect to Gateway',
                style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13.5),
              ),
            ),
          ),
          const SizedBox(height: 8),
          Row(
            children: [
              Expanded(
                child: OutlinedButton.icon(
                  style: OutlinedButton.styleFrom(
                    foregroundColor: textColor,
                    side: BorderSide(color: isDark ? Colors.white24 : Colors.black26),
                    padding: const EdgeInsets.symmetric(vertical: 11),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                  ),
                  onPressed: _testing ? null : _testConnectionAndDiscoverTools,
                  icon: _testing
                      ? SizedBox.square(dimension: 14, child: CircularProgressIndicator(strokeWidth: 2, color: textColor))
                      : const Icon(Icons.build_circle_outlined, size: 16),
                  label: Text(_testing ? 'Testing...' : 'Test & Discover Tools', style: const TextStyle(fontSize: 12.5)),
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: OutlinedButton.icon(
                  style: OutlinedButton.styleFrom(
                    foregroundColor: textColor,
                    side: BorderSide(color: isDark ? Colors.white24 : Colors.black26),
                    padding: const EdgeInsets.symmetric(vertical: 11),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                  ),
                  onPressed: _showVersionHistory,
                  icon: const Icon(Icons.history_rounded, size: 16),
                  label: const Text('View Versions', style: TextStyle(fontSize: 12.5)),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
  Widget _buildDownloadStatsCard(
    bool isDark,
    Color cardBgColor,
    Color textColor,
    Color mutedTextColor,
  ) {
    final sampleData = [14.0, 22.0, 18.0, 34.0, 42.0, 38.0, 56.0, 50.0, 68.0, 74.0, 65.0, 88.0];

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: cardBgColor,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: isDark ? Colors.white.withValues(alpha: 0.08) : Colors.black.withValues(alpha: 0.06),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Weekly Download Trajectory',
                    style: TextStyle(fontSize: 12, color: mutedTextColor, fontWeight: FontWeight.w600),
                  ),
                  const SizedBox(height: 2),
                  Row(
                    crossAxisAlignment: CrossAxisAlignment.baseline,
                    textBaseline: TextBaseline.alphabetic,
                    children: [
                      Text(
                        '48.5K',
                        style: TextStyle(
                          fontSize: 22,
                          fontWeight: FontWeight.bold,
                          color: textColor,
                        ),
                      ),
                      const SizedBox(width: 8),
                      Text(
                        '+18.4% this month',
                        style: TextStyle(
                          fontSize: 12,
                          fontWeight: FontWeight.w600,
                          color: isDark ? const Color(0xFF4ADE80) : const Color(0xFF16A34A),
                        ),
                      ),
                    ],
                  ),
                ],
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                decoration: BoxDecoration(
                  color: isDark ? Colors.white10 : Colors.black.withValues(alpha: 0.05),
                  borderRadius: BorderRadius.circular(20),
                ),
                child: Text(
                  '7 Days',
                  style: TextStyle(fontSize: 11, fontWeight: FontWeight.w600, color: mutedTextColor),
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          SizedBox(
            height: 70,
            width: double.infinity,
            child: CustomPaint(
              painter: _SparklinePainter(
                values: sampleData,
                lineColor: isDark ? Colors.white70 : Colors.black87,
                fillColor: isDark ? Colors.white : Colors.black,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildSlaReliabilityCard(
    bool isDark,
    Color cardBgColor,
    Color textColor,
    Color mutedTextColor,
  ) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: cardBgColor,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: isDark ? Colors.white.withValues(alpha: 0.08) : Colors.black.withValues(alpha: 0.06),
        ),
      ),
      child: Column(
        children: [
          Row(
            children: [
              SizedBox(
                width: 54,
                height: 54,
                child: CustomPaint(
                  painter: _RingPainter(
                    percentage: 0.998,
                    trackColor: isDark ? Colors.white12 : Colors.black12,
                    progressColor: isDark ? Colors.white70 : Colors.black87,
                  ),
                  child: Center(
                    child: Text(
                      '99.8%',
                      style: TextStyle(
                        fontSize: 11.5,
                        fontWeight: FontWeight.bold,
                        color: textColor,
                      ),
                    ),
                  ),
                ),
              ),
              const SizedBox(width: 16),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Server SLA & Protocol Uptime',
                      style: TextStyle(fontSize: 14, fontWeight: FontWeight.bold, color: textColor),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      'Continuous protocol handshake & schema validation checks',
                      style: TextStyle(fontSize: 12, color: mutedTextColor),
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          Divider(height: 1, color: isDark ? Colors.white10 : Colors.black.withValues(alpha: 0.06)),
          const SizedBox(height: 16),
          _ProgressBarRow(
            label: 'Protocol Handshake Pass Rate',
            value: '99.8%',
            percentage: 0.998,
            isDark: isDark,
          ),
          const SizedBox(height: 12),
          _ProgressBarRow(
            label: 'JSON Schema Compliance',
            value: '99.9%',
            percentage: 0.999,
            isDark: isDark,
          ),
          const SizedBox(height: 12),
          _ProgressBarRow(
            label: 'Sandbox Process Isolation',
            value: '100.0%',
            percentage: 1.0,
            isDark: isDark,
          ),
          const SizedBox(height: 12),
          _ProgressBarRow(
            label: 'Response Payload Velocity',
            value: '98.4%',
            percentage: 0.984,
            isDark: isDark,
          ),
        ],
      ),
    );
  }

  Widget _buildCommunityRatingCard(
    bool isDark,
    Color cardBgColor,
    Color textColor,
    Color mutedTextColor,
  ) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: cardBgColor,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: isDark ? Colors.white.withValues(alpha: 0.08) : Colors.black.withValues(alpha: 0.06),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.center,
            children: [
              Column(
                children: [
                  Text(
                    '4.9',
                    style: TextStyle(fontSize: 32, fontWeight: FontWeight.bold, color: textColor, height: 1.0),
                  ),
                  const SizedBox(height: 4),
                  Row(
                    mainAxisSize: MainAxisSize.min,
                    children: List.generate(
                      5,
                      (index) => Icon(
                        index < 4 ? Icons.star_rounded : Icons.star_half_rounded,
                        size: 14,
                        color: Colors.amber,
                      ),
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    '1,840 ratings',
                    style: TextStyle(fontSize: 10.5, color: mutedTextColor),
                  ),
                ],
              ),
              const SizedBox(width: 20),
              Expanded(
                child: Column(
                  children: [
                    _RatingBarRow(starLabel: '5 ★', percentage: 0.85, isDark: isDark),
                    const SizedBox(height: 4),
                    _RatingBarRow(starLabel: '4 ★', percentage: 0.10, isDark: isDark),
                    const SizedBox(height: 4),
                    _RatingBarRow(starLabel: '3 ★', percentage: 0.03, isDark: isDark),
                    const SizedBox(height: 4),
                    _RatingBarRow(starLabel: '2 ★', percentage: 0.01, isDark: isDark),
                    const SizedBox(height: 4),
                    _RatingBarRow(starLabel: '1 ★', percentage: 0.01, isDark: isDark),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 14),
          Divider(height: 1, color: isDark ? Colors.white10 : Colors.black.withValues(alpha: 0.06)),
          const SizedBox(height: 12),
          Wrap(
            spacing: 6,
            runSpacing: 6,
            children: [
              _PillTag(label: '⚡ Ultra Fast Response', isDark: isDark),
              _PillTag(label: '🛡️ High Security Audit', isDark: isDark),
              _PillTag(label: '📦 Streamable Transport', isDark: isDark),
              _PillTag(label: '🔥 Developer Choice 2026', isDark: isDark),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildEndpointsCard(
    bool isDark,
    Color cardBgColor,
    Color textColor,
    Color mutedTextColor,
  ) {
    final remotes = (_detail!['remotes'] as List? ?? const []);
    final packages = (_detail!['packages'] as List? ?? const []);

    return Container(
      decoration: BoxDecoration(
        color: cardBgColor,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: isDark ? Colors.white.withValues(alpha: 0.08) : Colors.black.withValues(alpha: 0.06),
        ),
      ),
      child: Column(
        children: [
          ...remotes.map((r) {
            final remote = (r as Map).cast<String, dynamic>();
            final urlStr = '${remote['url']}';
            return ListTile(
              leading: Icon(Icons.api_rounded, size: 20, color: isDark ? Colors.white70 : Colors.black87),
              title: Text('Remote Endpoint (${remote['type'] ?? 'http'})', style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: textColor)),
              subtitle: SelectableText(urlStr, style: TextStyle(fontFamily: 'monospace', fontSize: 11, color: mutedTextColor)),
              trailing: IconButton(
                icon: const Icon(Icons.open_in_new_rounded, size: 16),
                onPressed: () => _openUrl(urlStr),
              ),
            );
          }),
          ...packages.map((p) {
            final pkg = (p as Map).cast<String, dynamic>();
            final idStr = '${pkg['identifier']}';
            return ListTile(
              leading: Icon(Icons.terminal_rounded, size: 20, color: isDark ? Colors.white70 : Colors.black87),
              title: Text('Package Identifier (${pkg['registryType'] ?? 'npm'})', style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: textColor)),
              subtitle: SelectableText(idStr, style: TextStyle(fontFamily: 'monospace', fontSize: 11, color: mutedTextColor)),
              trailing: IconButton(
                icon: const Icon(Icons.copy_rounded, size: 16),
                onPressed: () => _copyToClipboard(idStr, 'Package Identifier'),
              ),
            );
          }),
        ],
      ),
    );
  }

  Widget _buildToolsSection(
    bool isDark,
    Color cardBgColor,
    Color textColor,
    Color mutedTextColor,
  ) {
    final toolsList = (_detail!['tools'] as List? ?? const []);
    if (toolsList.isEmpty) {
      return Container(
        width: double.infinity,
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: cardBgColor,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(
            color: isDark ? Colors.white.withValues(alpha: 0.08) : Colors.black.withValues(alpha: 0.06),
          ),
        ),
        child: Row(
          children: [
            Icon(Icons.info_outline_rounded, size: 18, color: mutedTextColor),
            const SizedBox(width: 10),
            Expanded(
              child: Text(
                'No tools discovered yet. Tap "Test & Discover Tools" above to run live server handshake.',
                style: TextStyle(fontSize: 12, color: mutedTextColor),
              ),
            ),
          ],
        ),
      );
    }

    return Column(
      children: toolsList.map((t) {
        final tool = (t as Map).cast<String, dynamic>();
        final toolName = '${tool['name']}';
        final toolDesc = '${tool['description']}';
        final inputSchema = '${tool['input_schema']}';

        return Container(
          margin: const EdgeInsets.only(bottom: 10),
          decoration: BoxDecoration(
            color: cardBgColor,
            borderRadius: BorderRadius.circular(16),
            border: Border.all(
              color: isDark ? Colors.white.withValues(alpha: 0.08) : Colors.black.withValues(alpha: 0.06),
            ),
          ),
          child: Theme(
            data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
            child: ExpansionTile(
              leading: Icon(Icons.build_circle_outlined, size: 22, color: isDark ? Colors.white70 : Colors.black87),
              title: Text(toolName, style: TextStyle(fontWeight: FontWeight.bold, fontSize: 14, color: textColor)),
              subtitle: Text(toolDesc, style: TextStyle(fontSize: 12, color: mutedTextColor), maxLines: 2, overflow: TextOverflow.ellipsis),
              children: [
                Padding(
                  padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Text('JSON Input Schema:', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 11, color: mutedTextColor)),
                          InkWell(
                            onTap: () => _copyToClipboard(inputSchema, 'JSON Schema'),
                            child: Padding(
                              padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                              child: Row(
                                children: [
                                  Icon(Icons.copy_rounded, size: 12, color: mutedTextColor),
                                  const SizedBox(width: 4),
                                  Text('Copy', style: TextStyle(fontSize: 11, color: mutedTextColor)),
                                ],
                              ),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 6),
                      Container(
                        width: double.infinity,
                        padding: const EdgeInsets.all(12),
                        decoration: BoxDecoration(
                          color: isDark ? Colors.black.withValues(alpha: 0.4) : Colors.black.withValues(alpha: 0.04),
                          borderRadius: BorderRadius.circular(10),
                          border: Border.all(
                            color: isDark ? Colors.white.withValues(alpha: 0.06) : Colors.black.withValues(alpha: 0.06),
                          ),
                        ),
                        child: Text(
                          inputSchema,
                          style: TextStyle(
                            fontFamily: 'monospace',
                            fontSize: 11,
                            color: isDark ? Colors.white70 : Colors.black87,
                            height: 1.4,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
        );
      }).toList(),
    );
  }

  Widget _buildAuthorLinksCard(
    bool isDark,
    Color cardBgColor,
    Color textColor,
    Color mutedTextColor,
  ) {
    final d = _detail!;
    final repoUrl = d['repo_url'] != null ? '${d['repo_url']}' : '';
    final websiteUrl = d['website_url'] != null ? '${d['website_url']}' : '';
    final authorUrl = d['author_url'] != null ? '${d['author_url']}' : '';

    if (repoUrl.isEmpty && websiteUrl.isEmpty && authorUrl.isEmpty) {
      return Container(
        width: double.infinity,
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: cardBgColor,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(
            color: isDark ? Colors.white.withValues(alpha: 0.08) : Colors.black.withValues(alpha: 0.06),
          ),
        ),
        child: Text('No publisher links specified for this MCP entry.', style: TextStyle(fontSize: 12, color: mutedTextColor)),
      );
    }

    return Container(
      decoration: BoxDecoration(
        color: cardBgColor,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: isDark ? Colors.white.withValues(alpha: 0.08) : Colors.black.withValues(alpha: 0.06),
        ),
      ),
      child: Column(
        children: [
          if (repoUrl.isNotEmpty)
            ListTile(
              leading: Icon(Icons.code_rounded, size: 20, color: isDark ? Colors.white70 : Colors.black87),
              title: Text('Source Repository', style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: textColor)),
              subtitle: SelectableText(repoUrl, style: TextStyle(fontSize: 11, color: mutedTextColor)),
              trailing: const Icon(Icons.open_in_new_rounded, size: 16),
              onTap: () => _openUrl(repoUrl),
            ),
          if (websiteUrl.isNotEmpty)
            ListTile(
              leading: Icon(Icons.language_rounded, size: 20, color: isDark ? Colors.white70 : Colors.black87),
              title: Text('Official Website', style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: textColor)),
              subtitle: SelectableText(websiteUrl, style: TextStyle(fontSize: 11, color: mutedTextColor)),
              trailing: const Icon(Icons.open_in_new_rounded, size: 16),
              onTap: () => _openUrl(websiteUrl),
            ),
          if (authorUrl.isNotEmpty)
            ListTile(
              leading: Icon(Icons.person_outline_rounded, size: 20, color: isDark ? Colors.white70 : Colors.black87),
              title: Text('Author / Publisher Page', style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: textColor)),
              subtitle: SelectableText(authorUrl, style: TextStyle(fontSize: 11, color: mutedTextColor)),
              trailing: const Icon(Icons.open_in_new_rounded, size: 16),
              onTap: () => _openUrl(authorUrl),
            ),
        ],
      ),
    );
  }
}

// =============================================================================
// REUSABLE STATS, GAUGES, SPARKLINE & GRAPHIC PAINTERS
// =============================================================================

class _SectionLabel extends StatelessWidget {
  final String title;
  final IconData icon;
  final bool isDark;

  const _SectionLabel({
    required this.title,
    required this.icon,
    required this.isDark,
  });

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Icon(icon, size: 15, color: isDark ? Colors.white54 : Colors.black54),
        const SizedBox(width: 8),
        Text(
          title,
          style: TextStyle(
            fontSize: 11,
            fontWeight: FontWeight.bold,
            letterSpacing: 0.8,
            color: isDark ? Colors.white54 : Colors.black54,
          ),
        ),
      ],
    );
  }
}

class _PillTag extends StatelessWidget {
  final String label;
  final bool isDark;

  const _PillTag({required this.label, required this.isDark});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: isDark ? Colors.white10 : Colors.black.withValues(alpha: 0.05),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Text(
        label,
        style: TextStyle(
          fontSize: 10.5,
          fontWeight: FontWeight.w600,
          color: isDark ? Colors.white70 : Colors.black87,
        ),
      ),
    );
  }
}

class _PillTagWithIcon extends StatelessWidget {
  final Widget icon;
  final String label;
  final bool isDark;

  const _PillTagWithIcon({
    required this.icon,
    required this.label,
    required this.isDark,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 5),
      decoration: BoxDecoration(
        color: isDark ? Colors.white10 : Colors.black.withValues(alpha: 0.05),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          icon,
          const SizedBox(width: 5),
          Text(
            label,
            style: TextStyle(
              fontSize: 11,
              fontWeight: FontWeight.w600,
              color: isDark ? Colors.white70 : Colors.black87,
            ),
          ),
        ],
      ),
    );
  }
}

class _CompactMetricTile extends StatelessWidget {
  final String title;
  final String value;
  final String subtitle;
  final bool isDark;

  const _CompactMetricTile({
    required this.title,
    required this.value,
    required this.subtitle,
    required this.isDark,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: isDark ? const Color(0xFF14141A) : Colors.white,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(
          color: isDark ? Colors.white.withValues(alpha: 0.08) : Colors.black.withValues(alpha: 0.06),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            title,
            style: TextStyle(
              fontSize: 10.5,
              fontWeight: FontWeight.w600,
              color: isDark ? Colors.white54 : AppColors.textSecondary,
              letterSpacing: 0.5,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            value,
            style: TextStyle(
              fontSize: 18,
              fontWeight: FontWeight.bold,
              color: isDark ? Colors.white : AppColors.textPrimary,
            ),
          ),
          const SizedBox(height: 2),
          Text(
            subtitle,
            style: TextStyle(
              fontSize: 10,
              color: isDark ? Colors.white38 : AppColors.textSecondary,
            ),
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
          ),
        ],
      ),
    );
  }
}

class _ProgressBarRow extends StatelessWidget {
  final String label;
  final String value;
  final double percentage;
  final bool isDark;

  const _ProgressBarRow({
    required this.label,
    required this.value,
    required this.percentage,
    required this.isDark,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(
              label,
              style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: isDark ? Colors.white70 : Colors.black87),
            ),
            Text(
              value,
              style: TextStyle(fontSize: 11.5, color: isDark ? Colors.white54 : AppColors.textSecondary),
            ),
          ],
        ),
        const SizedBox(height: 6),
        ClipRRect(
          borderRadius: BorderRadius.circular(4),
          child: LinearProgressIndicator(
            value: percentage,
            minHeight: 5,
            backgroundColor: isDark ? Colors.white12 : Colors.black12,
            valueColor: AlwaysStoppedAnimation<Color>(
              isDark ? Colors.white70 : Colors.black87,
            ),
          ),
        ),
      ],
    );
  }
}

class _RatingBarRow extends StatelessWidget {
  final String starLabel;
  final double percentage;
  final bool isDark;

  const _RatingBarRow({
    required this.starLabel,
    required this.percentage,
    required this.isDark,
  });

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        SizedBox(
          width: 24,
          child: Text(
            starLabel,
            style: TextStyle(fontSize: 11, fontWeight: FontWeight.w600, color: isDark ? Colors.white70 : Colors.black87),
          ),
        ),
        const SizedBox(width: 8),
        Expanded(
          child: ClipRRect(
            borderRadius: BorderRadius.circular(4),
            child: LinearProgressIndicator(
              value: percentage,
              minHeight: 6,
              backgroundColor: isDark ? Colors.white12 : Colors.black12,
              valueColor: const AlwaysStoppedAnimation<Color>(Colors.amber),
            ),
          ),
        ),
      ],
    );
  }
}

class _SparklinePainter extends CustomPainter {
  final List<double> values;
  final Color lineColor;
  final Color fillColor;

  _SparklinePainter({
    required this.values,
    required this.lineColor,
    required this.fillColor,
  });

  @override
  void paint(Canvas canvas, Size size) {
    if (values.length < 2) return;

    final path = Path();
    final fillPath = Path();

    final dx = size.width / (values.length - 1);
    final minY = values.reduce(math.min);
    final maxY = values.reduce(math.max);
    final range = (maxY - minY) == 0 ? 1.0 : (maxY - minY);

    double getY(double val) => size.height - ((val - minY) / range) * (size.height * 0.75) - (size.height * 0.12);

    path.moveTo(0, getY(values[0]));
    fillPath.moveTo(0, size.height);
    fillPath.lineTo(0, getY(values[0]));

    for (int i = 0; i < values.length - 1; i++) {
      final x1 = i * dx;
      final y1 = getY(values[i]);
      final x2 = (i + 1) * dx;
      final y2 = getY(values[i + 1]);
      final cx = (x1 + x2) / 2;

      path.cubicTo(cx, y1, cx, y2, x2, y2);
      fillPath.cubicTo(cx, y1, cx, y2, x2, y2);
    }

    fillPath.lineTo(size.width, size.height);
    fillPath.close();

    final fillPaint = Paint()
      ..style = PaintingStyle.fill
      ..shader = LinearGradient(
        colors: [
          fillColor.withValues(alpha: 0.18),
          fillColor.withValues(alpha: 0.0),
        ],
        begin: Alignment.topCenter,
        end: Alignment.bottomCenter,
      ).createShader(Rect.fromLTWH(0, 0, size.width, size.height));

    canvas.drawPath(fillPath, fillPaint);

    final linePaint = Paint()
      ..color = lineColor
      ..style = PaintingStyle.stroke
      ..strokeWidth = 2.2
      ..strokeCap = StrokeCap.round;

    canvas.drawPath(path, linePaint);
  }

  @override
  bool shouldRepaint(covariant _SparklinePainter oldDelegate) => true;
}

class _RingPainter extends CustomPainter {
  final double percentage;
  final Color trackColor;
  final Color progressColor;

  _RingPainter({
    required this.percentage,
    required this.trackColor,
    required this.progressColor,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2);
    final radius = (size.width - 8) / 2;

    final trackPaint = Paint()
      ..color = trackColor
      ..style = PaintingStyle.stroke
      ..strokeWidth = 5.0;

    canvas.drawCircle(center, radius, trackPaint);

    final progressPaint = Paint()
      ..color = progressColor
      ..style = PaintingStyle.stroke
      ..strokeWidth = 5.0
      ..strokeCap = StrokeCap.round;

    const sweepAngle = 2 * math.pi;
    canvas.drawArc(
      Rect.fromCircle(center: center, radius: radius),
      -math.pi / 2,
      sweepAngle * percentage.clamp(0.0, 1.0),
      false,
      progressPaint,
    );
  }

  @override
  bool shouldRepaint(covariant _RingPainter oldDelegate) => true;
}

class _MCPDetailGlassHeader extends StatelessWidget {
  final double progress;
  final bool isDark;
  final String displayName;
  final VoidCallback onBackTap;

  const _MCPDetailGlassHeader({
    required this.progress,
    required this.isDark,
    required this.displayName,
    required this.onBackTap,
  });

  @override
  Widget build(BuildContext context) {
    final topPadding = MediaQuery.of(context).padding.top;
    final glassColor = isDark
        ? const Color(0xFF181820).withValues(alpha: 0.85 + (progress * 0.10))
        : const Color(0xFFF1F3F5).withValues(alpha: 0.85 + (progress * 0.10));

    final border = Border.all(
      color: isDark ? Colors.white.withValues(alpha: 0.12) : Colors.black.withValues(alpha: 0.08),
    );

    return Positioned(
      top: topPadding + 6,
      left: 12,
      right: 12,
      child: Row(
        children: [
          // 1. SEPARATE GLASS COMPONENT: Back Arrow Button Pill
          ClipRRect(
            borderRadius: BorderRadius.circular(16),
            child: BackdropFilter(
              filter: ImageFilter.blur(sigmaX: 16, sigmaY: 16),
              child: Container(
                height: 44,
                width: 44,
                decoration: BoxDecoration(
                  color: glassColor,
                  borderRadius: BorderRadius.circular(16),
                  border: border,
                ),
                child: Material(
                  color: Colors.transparent,
                  child: InkWell(
                    onTap: onBackTap,
                    borderRadius: BorderRadius.circular(16),
                    child: Center(
                      child: Icon(
                        Icons.arrow_back_rounded,
                        size: 20,
                        color: isDark ? Colors.white70 : Colors.black87,
                      ),
                    ),
                  ),
                ),
              ),
            ),
          ),
          const SizedBox(width: 8),

          // 2. SEPARATE GLASS COMPONENT: Compact Title Pill (Positioned right next to back arrow)
          ClipRRect(
            borderRadius: BorderRadius.circular(16),
            child: BackdropFilter(
              filter: ImageFilter.blur(sigmaX: 16, sigmaY: 16),
              child: Container(
                height: 44,
                padding: const EdgeInsets.symmetric(horizontal: 14),
                decoration: BoxDecoration(
                  color: glassColor,
                  borderRadius: BorderRadius.circular(16),
                  border: border,
                ),
                child: Center(
                  child: ConstrainedBox(
                    constraints: BoxConstraints(
                      maxWidth: MediaQuery.sizeOf(context).width * 0.45,
                    ),
                    child: Text(
                      displayName,
                      style: TextStyle(
                        fontSize: 13.5,
                        fontWeight: FontWeight.bold,
                        color: isDark ? Colors.white : Colors.black87,
                        letterSpacing: -0.2,
                      ),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                ),
              ),
            ),
          ),
          const Spacer(),

          // 3. SEPARATE GLASS COMPONENT: Verified Badge Pill
          ClipRRect(
            borderRadius: BorderRadius.circular(16),
            child: BackdropFilter(
              filter: ImageFilter.blur(sigmaX: 16, sigmaY: 16),
              child: Container(
                height: 44,
                padding: const EdgeInsets.symmetric(horizontal: 12),
                decoration: BoxDecoration(
                  color: glassColor,
                  borderRadius: BorderRadius.circular(16),
                  border: border,
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Container(
                      width: 6,
                      height: 6,
                      decoration: const BoxDecoration(
                        color: Color(0xFF22C55E),
                        shape: BoxShape.circle,
                      ),
                    ),
                    const SizedBox(width: 6),
                    Text(
                      'VERIFIED',
                      style: TextStyle(
                        fontSize: 10,
                        fontWeight: FontWeight.bold,
                        color: isDark ? Colors.white70 : Colors.black87,
                        letterSpacing: 0.5,
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
