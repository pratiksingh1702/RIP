import 'dart:math' as math;
import 'dart:ui';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/design/app_colors.dart';
import '../providers/connection_provider.dart';
import '../providers/project_provider.dart';
import 'mcp_detail_screen.dart';

class MCPMarketplaceScreen extends ConsumerStatefulWidget {
  const MCPMarketplaceScreen({super.key});

  @override
  ConsumerState<MCPMarketplaceScreen> createState() => _MCPMarketplaceScreenState();
}

class _MCPMarketplaceScreenState extends ConsumerState<MCPMarketplaceScreen> {
  final ScrollController _scrollController = ScrollController();
  final TextEditingController _searchController = TextEditingController();

  double _headerT = 0.0;
  bool _showStats = false;
  String _selectedCategory = 'all';
  List<Map<String, dynamic>> _sources = [];
  bool _loading = true;
  String? _error;
  String? _installingSourceId;
  final bool _includeUnverified = true;

  int _currentPage = 1;
  bool _hasMore = true;

  static final Map<String, List<Map<String, dynamic>>> _marketplaceCache = {};

  final List<Map<String, dynamic>> _categories = const [
    {'id': 'all', 'label': 'All Tools', 'icon': Icons.apps_rounded},
    {'id': 'code', 'label': 'Code & Git', 'icon': Icons.code_rounded},
    {'id': 'database', 'label': 'Databases', 'icon': Icons.storage_rounded},
    {'id': 'tickets', 'label': 'Tickets & Tasks', 'icon': Icons.assignment_rounded},
    {'id': 'docs', 'label': 'Docs & Knowledge', 'icon': Icons.description_rounded},
    {'id': 'communication', 'label': 'Chat & Team', 'icon': Icons.chat_rounded},
    {'id': 'search', 'label': 'Web Search', 'icon': Icons.search_rounded},
    {'id': 'infrastructure', 'label': 'Infrastructure', 'icon': Icons.cloud_rounded},
    {'id': 'analytics', 'label': 'Analytics', 'icon': Icons.insights_rounded},
    {'id': 'payments', 'label': 'Payments & CRM', 'icon': Icons.payments_rounded},
    {'id': 'ai', 'label': 'AI & Models', 'icon': Icons.psychology_rounded},
  ];

  @override
  void initState() {
    super.initState();
    _scrollController.addListener(_onScroll);
    _loadMarketplace();
  }

  @override
  void dispose() {
    _scrollController.removeListener(_onScroll);
    _scrollController.dispose();
    _searchController.dispose();
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

  String _getCacheKey() {
    final search = _searchController.text.trim().toLowerCase();
    return 'cat:$_selectedCategory|unv:$_includeUnverified|search:$search|page:$_currentPage';
  }

  Future<void> _loadMarketplace({bool refresh = false}) async {
    final cacheKey = _getCacheKey();
    if (refresh) {
      _currentPage = 1;
      _marketplaceCache.remove(cacheKey);
    }

    if (!refresh && _marketplaceCache.containsKey(cacheKey)) {
      setState(() {
        _sources = _marketplaceCache[cacheKey]!;
        _loading = false;
        _error = null;
      });
      return;
    }

    setState(() {
      _loading = true;
      _error = null;
    });

    try {
      final client = ref.read(ripClientProvider);
      final result = await client.getGatewayMarketplace(
        category: _selectedCategory == 'all' ? null : _selectedCategory,
        search: _searchController.text.trim().isEmpty ? null : _searchController.text.trim(),
        includeUnverified: _includeUnverified,
        page: _currentPage,
        limit: 30,
      );
      final rawList = (result['servers'] ?? result['sources']) as List? ?? const [];
      final parsed = rawList.map((e) => (e as Map).cast<String, dynamic>()).toList();
      _hasMore = result['has_more'] as bool? ?? false;
      _marketplaceCache[cacheKey] = parsed;

      setState(() {
        _sources = parsed;
        _loading = false;
      });
    } catch (e) {
      if (mounted) {
        setState(() {
          _error = 'Failed to load MCP Marketplace: $e';
          _loading = false;
        });
      }
    }
  }

  Future<void> _installSource(Map<String, dynamic> source) async {
    final sourceId = '${source['id']}';
    final projectId = ref.read(activeProjectIdProvider);
    setState(() => _installingSourceId = sourceId);
    try {
      final client = ref.read(ripClientProvider);
      await client.installGatewayMarketplaceSource(sourceId, projectId: projectId);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Row(
              children: [
                const Icon(Icons.check_circle_rounded, color: Colors.greenAccent, size: 18),
                const SizedBox(width: 8),
                Expanded(child: Text('${source['name']} installed successfully!')),
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
            content: Text('Installation failed: $e'),
            backgroundColor: Colors.redAccent,
            behavior: SnackBarBehavior.floating,
          ),
        );
      }
    } finally {
      if (mounted) setState(() => _installingSourceId = null);
    }
  }

  void _openDetail(Map<String, dynamic> source) {
    HapticFeedback.selectionClick();
    Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => MCPDetailScreen(sourceId: '${source['id']}'),
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

    return Scaffold(
      extendBodyBehindAppBar: true,
      backgroundColor: bgColor,
      body: Stack(
        children: [
          // 1. BACKGROUND BASE CANVAS
          ColoredBox(color: bgColor),

          // 2. INFINITE SCROLLABLE SINGLE BODY CONTENT
          SingleChildScrollView(
            controller: _scrollController,
            physics: const AlwaysScrollableScrollPhysics(parent: BouncingScrollPhysics()),
            padding: EdgeInsets.fromLTRB(
              16,
              topPadding + 76,
              16,
              bottomPadding + 90,
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // --- SECTION 1: SEARCH & FILTER HEADER CARD ---
                _buildSearchCard(isDark, textColor, mutedTextColor),
                const SizedBox(height: 12),

                // --- SECTION 2: HORIZONTAL CATEGORY FILTER CHIPS ---
                _buildCategoryFilterRow(isDark, mutedTextColor),
                const SizedBox(height: 16),

                // --- SECTION 3: MARKETPLACE SERVER CARDS LIST ---
                _SectionLabel(
                  title: 'AVAILABLE MCP SERVERS (${_sources.length})',
                  icon: Icons.hub_rounded,
                  isDark: isDark,
                ),
                const SizedBox(height: 4),

                if (_loading)
                  const Padding(
                    padding: EdgeInsets.all(40),
                    child: Center(child: CircularProgressIndicator(strokeWidth: 2, color: Colors.grey)),
                  )
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
                            onPressed: () => _loadMarketplace(refresh: true),
                            child: const Text('Retry Loading'),
                          ),
                        ],
                      ),
                    ),
                  )
                else if (_sources.isEmpty)
                  Container(
                    width: double.infinity,
                    padding: const EdgeInsets.all(24),
                    decoration: BoxDecoration(
                      color: cardBgColor,
                      borderRadius: BorderRadius.circular(16),
                      border: Border.all(
                        color: isDark ? Colors.white.withValues(alpha: 0.08) : Colors.black.withValues(alpha: 0.06),
                      ),
                    ),
                    child: Column(
                      children: [
                        Icon(Icons.search_off_rounded, size: 36, color: mutedTextColor),
                        const SizedBox(height: 10),
                        Text(
                          'No MCP servers found matching your query.',
                          style: TextStyle(fontSize: 13, color: mutedTextColor),
                          textAlign: TextAlign.center,
                        ),
                      ],
                    ),
                  )
                else
                  ListView.separated(
                    shrinkWrap: true,
                    padding: EdgeInsets.zero,
                    physics: const NeverScrollableScrollPhysics(),
                    itemCount: _sources.length,
                    separatorBuilder: (_, __) => const SizedBox(height: 12),
                    itemBuilder: (context, index) {
                      final source = _sources[index];
                      return _buildMarketplaceCard(source, isDark, cardBgColor, textColor, mutedTextColor);
                    },
                  ),
              ],
            ),
          ),

          // 3. FULL SCREEN DISMISS BACKDROP OVERLAY WHEN STATS ARE EXPANDED
          if (_showStats)
            Positioned.fill(
              child: GestureDetector(
                onTap: () {
                  HapticFeedback.selectionClick();
                  setState(() => _showStats = false);
                },
                behavior: HitTestBehavior.opaque,
                child: AnimatedContainer(
                  duration: const Duration(milliseconds: 200),
                  color: Colors.black.withValues(alpha: isDark ? 0.45 : 0.25),
                ),
              ),
            ),

          // 4. TOP FADE GRADIENT OVERLAY
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

          // 5. BOTTOM FADE GRADIENT OVERLAY
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

          // 6. EXPANDABLE STATS DROPDOWN PANEL UNDER APP BAR
          Positioned(
            top: topPadding + 56,
            left: 12,
            right: 12,
            child: AnimatedSize(
              duration: const Duration(milliseconds: 260),
              curve: Curves.easeOutCubic,
              child: _showStats
                  ? _buildExpandableStatsPanel(isDark, cardBgColor, textColor, mutedTextColor)
                  : const SizedBox.shrink(),
            ),
          ),

          // 7. FLOATING GLASSMORPHIC TOP HEADER BAR
          _MarketplaceGlassHeader(
            progress: _headerT,
            isDark: isDark,
            currentPage: _currentPage,
            showStats: _showStats,
            onBackTap: () {
              HapticFeedback.selectionClick();
              Navigator.of(context).pop();
            },
            onStatsTap: () {
              HapticFeedback.selectionClick();
              setState(() => _showStats = !_showStats);
            },
            onRefreshTap: () {
              if (_showStats) setState(() => _showStats = false);
              _loadMarketplace(refresh: true);
            },
          ),

          // 8. FLOATING GLASSMORPHIC BOTTOM PAGINATION BAR
          if (!_loading && _sources.isNotEmpty)
            _MarketplaceGlassBottomBar(
              currentPage: _currentPage,
              hasMore: _hasMore,
              isDark: isDark,
              onPrevTap: _currentPage > 1
                  ? () {
                      HapticFeedback.selectionClick();
                      if (_showStats) setState(() => _showStats = false);
                      setState(() => _currentPage--);
                      _loadMarketplace();
                    }
                  : null,
              onNextTap: _hasMore
                  ? () {
                      HapticFeedback.selectionClick();
                      if (_showStats) setState(() => _showStats = false);
                      setState(() => _currentPage++);
                      _loadMarketplace();
                    }
                  : null,
            ),
        ],
      ),
    );
  }

  Widget _buildSearchCard(
    bool isDark,
    Color textColor,
    Color mutedTextColor,
  ) {
    return Container(
      height: 42,
      padding: const EdgeInsets.symmetric(horizontal: 12),
      decoration: BoxDecoration(
        color: isDark
            ? const Color(0xFF14141A)
            : Colors.black.withValues(alpha: 0.04),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(
          color: isDark ? Colors.white.withValues(alpha: 0.08) : Colors.black.withValues(alpha: 0.06),
        ),
      ),
      child: Center(
        child: TextField(
          controller: _searchController,
          style: TextStyle(fontSize: 13, color: textColor),
          onSubmitted: (_) => _loadMarketplace(refresh: true),
          decoration: InputDecoration(
            isDense: true,
            filled: true,
            fillColor: Colors.transparent,
            contentPadding: EdgeInsets.zero,
            hintText: 'Search 1,200+ MCP servers (GitHub, Postgres, Slack...)',
            hintStyle: TextStyle(fontSize: 12, color: mutedTextColor),
            prefixIcon: Icon(Icons.search_rounded, size: 18, color: mutedTextColor),
            prefixIconConstraints: const BoxConstraints(minWidth: 30, minHeight: 0),
            suffixIcon: _searchController.text.isNotEmpty
                ? InkWell(
                    onTap: () {
                      _searchController.clear();
                      _loadMarketplace(refresh: true);
                    },
                    borderRadius: BorderRadius.circular(12),
                    child: Icon(Icons.clear_rounded, size: 16, color: mutedTextColor),
                  )
                : null,
            suffixIconConstraints: const BoxConstraints(minWidth: 26, minHeight: 0),
            border: InputBorder.none,
            enabledBorder: InputBorder.none,
            focusedBorder: InputBorder.none,
          ),
        ),
      ),
    );
  }

  Widget _buildCategoryFilterRow(bool isDark, Color mutedTextColor) {
    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      physics: const BouncingScrollPhysics(),
      child: Row(
        children: _categories.map((cat) {
          final isSelected = _selectedCategory == cat['id'];
          final catId = cat['id'] as String;
          final catLabel = cat['label'] as String;
          final catIcon = cat['icon'] as IconData;

          return Padding(
            padding: const EdgeInsets.only(right: 8),
            child: InkWell(
              onTap: () {
                HapticFeedback.selectionClick();
                if (_showStats) setState(() => _showStats = false);
                setState(() => _selectedCategory = catId);
                _loadMarketplace(refresh: true);
              },
              borderRadius: BorderRadius.circular(12),
              child: AnimatedContainer(
                duration: const Duration(milliseconds: 180),
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                decoration: BoxDecoration(
                  color: isSelected
                      ? (isDark ? Colors.white : Colors.black)
                      : (isDark ? const Color(0xFF14141A) : Colors.white),
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(
                    color: isSelected
                        ? (isDark ? Colors.white : Colors.black)
                        : (isDark ? Colors.white.withValues(alpha: 0.08) : Colors.black.withValues(alpha: 0.06)),
                  ),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(
                      catIcon,
                      size: 14,
                      color: isSelected
                          ? (isDark ? Colors.black : Colors.white)
                          : (isDark ? Colors.white70 : Colors.black87),
                    ),
                    const SizedBox(width: 6),
                    Text(
                      catLabel,
                      style: TextStyle(
                        fontSize: 12,
                        fontWeight: isSelected ? FontWeight.bold : FontWeight.w500,
                        color: isSelected
                            ? (isDark ? Colors.black : Colors.white)
                            : (isDark ? Colors.white70 : Colors.black87),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          );
        }).toList(),
      ),
    );
  }

  Widget _buildExpandableStatsPanel(
    bool isDark,
    Color cardBgColor,
    Color textColor,
    Color mutedTextColor,
  ) {
    final sampleData = [24.0, 36.0, 48.0, 42.0, 58.0, 64.0, 72.0, 80.0, 94.0, 110.0, 104.0, 128.0];

    return ClipRRect(
      borderRadius: BorderRadius.circular(20),
      child: BackdropFilter(
        filter: ImageFilter.blur(sigmaX: 20, sigmaY: 20),
        child: Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: isDark
                ? const Color(0xFF14141E).withValues(alpha: 0.95)
                : Colors.white.withValues(alpha: 0.95),
            borderRadius: BorderRadius.circular(20),
            border: Border.all(
              color: isDark ? Colors.white.withValues(alpha: 0.15) : Colors.black.withValues(alpha: 0.10),
            ),
            boxShadow: [
              BoxShadow(
                color: Colors.black.withValues(alpha: isDark ? 0.5 : 0.12),
                blurRadius: 24,
                offset: const Offset(0, 12),
              ),
            ],
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // PANEL HEADER TITLE WITH DISMISS X
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Row(
                    children: [
                      Icon(Icons.insights_rounded, size: 16, color: isDark ? const Color(0xFF4ADE80) : const Color(0xFF16A34A)),
                      const SizedBox(width: 8),
                      Text(
                        'GLOBAL MARKETPLACE TELEMETRY',
                        style: TextStyle(
                          fontSize: 11,
                          fontWeight: FontWeight.bold,
                          letterSpacing: 0.6,
                          color: isDark ? Colors.white70 : Colors.black87,
                        ),
                      ),
                    ],
                  ),
                  InkWell(
                    onTap: () {
                      HapticFeedback.selectionClick();
                      setState(() => _showStats = false);
                    },
                    borderRadius: BorderRadius.circular(12),
                    child: Padding(
                      padding: const EdgeInsets.all(4),
                      child: Icon(Icons.close_rounded, size: 18, color: mutedTextColor),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 14),

              // SPARKLINE TRAJECTORY CARD
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: isDark ? Colors.white.withValues(alpha: 0.05) : Colors.black.withValues(alpha: 0.04),
                  borderRadius: BorderRadius.circular(14),
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
                              'Marketplace Installs Trajectory',
                              style: TextStyle(fontSize: 11, color: mutedTextColor, fontWeight: FontWeight.w600),
                            ),
                            const SizedBox(height: 2),
                            Row(
                              crossAxisAlignment: CrossAxisAlignment.baseline,
                              textBaseline: TextBaseline.alphabetic,
                              children: [
                                Text(
                                  '485.2K',
                                  style: TextStyle(
                                    fontSize: 20,
                                    fontWeight: FontWeight.bold,
                                    color: textColor,
                                  ),
                                ),
                                const SizedBox(width: 8),
                                Text(
                                  '+24.8% growth',
                                  style: TextStyle(
                                    fontSize: 11.5,
                                    fontWeight: FontWeight.w600,
                                    color: isDark ? const Color(0xFF4ADE80) : const Color(0xFF16A34A),
                                  ),
                                ),
                              ],
                            ),
                          ],
                        ),
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                          decoration: BoxDecoration(
                            color: isDark ? Colors.white10 : Colors.black.withValues(alpha: 0.05),
                            borderRadius: BorderRadius.circular(16),
                          ),
                          child: Text(
                            '30 Days',
                            style: TextStyle(fontSize: 10, fontWeight: FontWeight.w600, color: mutedTextColor),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 12),
                    SizedBox(
                      height: 54,
                      width: double.infinity,
                      child: CustomPaint(
                        painter: _MarketplaceSparklinePainter(
                          values: sampleData,
                          lineColor: isDark ? Colors.white70 : Colors.black87,
                          fillColor: isDark ? Colors.white : Colors.black,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 12),

              // 4 METRIC TILES GRID
              Row(
                children: [
                  Expanded(
                    child: _CompactMetricTile(
                      title: 'TOTAL SERVERS',
                      value: '1,240',
                      subtitle: 'Official Registry',
                      isDark: isDark,
                    ),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: _CompactMetricTile(
                      title: 'DISCOVERED TOOLS',
                      value: '8,420',
                      subtitle: 'Live Handshake',
                      isDark: isDark,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              Row(
                children: [
                  Expanded(
                    child: _CompactMetricTile(
                      title: 'ACTIVE INTEGRATIONS',
                      value: '42.8K',
                      subtitle: 'Context Gateway',
                      isDark: isDark,
                    ),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: _CompactMetricTile(
                      title: 'REGISTRY SLA',
                      value: '99.9%',
                      subtitle: 'Continuous Sync',
                      isDark: isDark,
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildMarketplaceCard(
    Map<String, dynamic> source,
    bool isDark,
    Color cardBgColor,
    Color textColor,
    Color mutedTextColor,
  ) {
    final sourceId = '${source['id']}';
    final name = '${source['display_name'] ?? source['name']}';
    final description = '${source['description']}';
    final trustTier = source['trust_tier'] ?? (source['is_official'] == true ? 'community' : 'unverified');
    final tools = (source['tools'] as List? ?? const []);
    final toolCount = source['tool_count'] ?? (tools.isNotEmpty ? tools.length : 1);
    final isInstalling = _installingSourceId == sourceId;

    return Container(
      decoration: BoxDecoration(
        color: cardBgColor,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: isDark ? Colors.white.withValues(alpha: 0.08) : Colors.black.withValues(alpha: 0.06),
        ),
      ),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: () {
            if (_showStats) setState(() => _showStats = false);
            _openDetail(source);
          },
          borderRadius: BorderRadius.circular(16),
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Container(
                      padding: const EdgeInsets.all(10),
                      decoration: BoxDecoration(
                        color: isDark ? const Color(0xFF22222E) : const Color(0xFFEFEFF5),
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: Icon(
                        _categoryIcon('${source['category']}'),
                        color: isDark ? Colors.white70 : Colors.black87,
                        size: 22,
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            children: [
                              Expanded(
                                child: Text(
                                  name,
                                  style: TextStyle(
                                    fontSize: 15,
                                    fontWeight: FontWeight.bold,
                                    color: textColor,
                                    letterSpacing: -0.2,
                                  ),
                                  maxLines: 1,
                                  overflow: TextOverflow.ellipsis,
                                ),
                              ),
                              const SizedBox(width: 6),
                              _buildTrustBadge(trustTier, isDark),
                            ],
                          ),
                          const SizedBox(height: 4),
                          Text(
                            description,
                            maxLines: 2,
                            overflow: TextOverflow.ellipsis,
                            style: TextStyle(fontSize: 12, color: mutedTextColor, height: 1.35),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 14),
                Divider(height: 1, color: isDark ? Colors.white10 : Colors.black.withValues(alpha: 0.06)),
                const SizedBox(height: 12),
                Row(
                  children: [
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                      decoration: BoxDecoration(
                        color: isDark ? Colors.white10 : Colors.black.withValues(alpha: 0.05),
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Icon(Icons.build_circle_outlined, size: 13, color: mutedTextColor),
                          const SizedBox(width: 5),
                          Text(
                            '$toolCount tool(s) offered',
                            style: TextStyle(fontSize: 11, fontWeight: FontWeight.w600, color: mutedTextColor),
                          ),
                        ],
                      ),
                    ),
                    const Spacer(),
                    OutlinedButton.icon(
                      style: OutlinedButton.styleFrom(
                        foregroundColor: textColor,
                        side: BorderSide(color: isDark ? Colors.white24 : Colors.black26),
                        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                        minimumSize: Size.zero,
                        tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                      ),
                      onPressed: () {
                        if (_showStats) setState(() => _showStats = false);
                        _openDetail(source);
                      },
                      icon: const Icon(Icons.info_outline_rounded, size: 14),
                      label: const Text('Inspect', style: TextStyle(fontSize: 11.5, fontWeight: FontWeight.bold)),
                    ),
                    const SizedBox(width: 8),
                    ElevatedButton.icon(
                      style: ElevatedButton.styleFrom(
                        backgroundColor: isDark ? Colors.white : Colors.black,
                        foregroundColor: isDark ? Colors.black : Colors.white,
                        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                        minimumSize: Size.zero,
                        tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                        elevation: 0,
                      ),
                      onPressed: isInstalling
                          ? null
                          : () {
                              if (_showStats) setState(() => _showStats = false);
                              _installSource(source);
                            },
                      icon: isInstalling
                          ? SizedBox.square(dimension: 12, child: CircularProgressIndicator(strokeWidth: 2, color: isDark ? Colors.black : Colors.white))
                          : const Icon(Icons.add_circle_outline_rounded, size: 14),
                      label: Text(
                        isInstalling ? 'Installing' : 'Connect',
                        style: const TextStyle(fontSize: 11.5, fontWeight: FontWeight.bold),
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildTrustBadge(String tier, bool isDark) {
    Color bg;
    Color fg;
    String label;
    IconData icon;

    switch (tier.toLowerCase()) {
      case 'verified':
        bg = isDark ? const Color(0xFF14301A) : const Color(0xFFDCFCE7);
        fg = isDark ? const Color(0xFF4ADE80) : const Color(0xFF16A34A);
        label = 'Verified';
        icon = Icons.verified_rounded;
        break;
      case 'community':
        bg = isDark ? const Color(0xFF1F2937) : const Color(0xFFF3F4F6);
        fg = isDark ? Colors.white70 : Colors.black87;
        label = 'Community';
        icon = Icons.people_outline_rounded;
        break;
      default:
        bg = isDark ? const Color(0xFF332014) : const Color(0xFFFFEDD5);
        fg = isDark ? const Color(0xFFFB923C) : const Color(0xFFEA580C);
        label = 'Unverified';
        icon = Icons.warning_amber_rounded;
        break;
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 3),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 11, color: fg),
          const SizedBox(width: 4),
          Text(
            label,
            style: TextStyle(fontSize: 10, fontWeight: FontWeight.bold, color: fg),
          ),
        ],
      ),
    );
  }

  IconData _categoryIcon(String cat) {
    switch (cat.toLowerCase()) {
      case 'code':
        return Icons.code_rounded;
      case 'database':
        return Icons.storage_rounded;
      case 'tickets':
        return Icons.assignment_rounded;
      case 'docs':
        return Icons.description_rounded;
      case 'communication':
        return Icons.chat_rounded;
      case 'search':
        return Icons.search_rounded;
      case 'infrastructure':
        return Icons.cloud_rounded;
      case 'analytics':
        return Icons.insights_rounded;
      case 'payments':
        return Icons.payments_rounded;
      case 'ai':
        return Icons.psychology_rounded;
      default:
        return Icons.hub_rounded;
    }
  }
}

// =============================================================================
// REUSABLE STATS, SPARKLINE & FLOATING GLASS HEADER / BOTTOM BAR
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
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: isDark ? const Color(0xFF1B1B26) : Colors.white,
        borderRadius: BorderRadius.circular(12),
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
              fontSize: 10,
              fontWeight: FontWeight.w600,
              color: isDark ? Colors.white54 : AppColors.textSecondary,
              letterSpacing: 0.5,
            ),
          ),
          const SizedBox(height: 3),
          Text(
            value,
            style: TextStyle(
              fontSize: 16,
              fontWeight: FontWeight.bold,
              color: isDark ? Colors.white : AppColors.textPrimary,
            ),
          ),
          const SizedBox(height: 2),
          Text(
            subtitle,
            style: TextStyle(
              fontSize: 9.5,
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

class _MarketplaceSparklinePainter extends CustomPainter {
  final List<double> values;
  final Color lineColor;
  final Color fillColor;

  _MarketplaceSparklinePainter({
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
  bool shouldRepaint(covariant _MarketplaceSparklinePainter oldDelegate) => true;
}

class _MarketplaceGlassHeader extends StatelessWidget {
  final double progress;
  final bool isDark;
  final int currentPage;
  final bool showStats;
  final VoidCallback onBackTap;
  final VoidCallback onStatsTap;
  final VoidCallback onRefreshTap;

  const _MarketplaceGlassHeader({
    required this.progress,
    required this.isDark,
    required this.currentPage,
    required this.showStats,
    required this.onBackTap,
    required this.onStatsTap,
    required this.onRefreshTap,
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
                      maxWidth: MediaQuery.sizeOf(context).width * 0.38,
                    ),
                    child: Text(
                      'MCP Marketplace',
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

          // 3. SEPARATE GLASS COMPONENT: Stats Toggle Glass Pill
          ClipRRect(
            borderRadius: BorderRadius.circular(16),
            child: BackdropFilter(
              filter: ImageFilter.blur(sigmaX: 16, sigmaY: 16),
              child: AnimatedContainer(
                duration: const Duration(milliseconds: 180),
                height: 44,
                width: 44,
                decoration: BoxDecoration(
                  color: showStats
                      ? (isDark ? Colors.white24 : Colors.black12)
                      : glassColor,
                  borderRadius: BorderRadius.circular(16),
                  border: Border.all(
                    color: showStats
                        ? (isDark ? const Color(0xFF4ADE80) : const Color(0xFF16A34A))
                        : (isDark ? Colors.white.withValues(alpha: 0.12) : Colors.black.withValues(alpha: 0.08)),
                  ),
                ),
                child: Material(
                  color: Colors.transparent,
                  child: InkWell(
                    onTap: onStatsTap,
                    borderRadius: BorderRadius.circular(16),
                    child: Center(
                      child: Icon(
                        Icons.insights_rounded,
                        size: 20,
                        color: showStats
                            ? (isDark ? const Color(0xFF4ADE80) : const Color(0xFF16A34A))
                            : (isDark ? Colors.white70 : Colors.black87),
                      ),
                    ),
                  ),
                ),
              ),
            ),
          ),
          const SizedBox(width: 8),

          // 4. SEPARATE GLASS COMPONENT: Refresh Action Glass Pill
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
                    onTap: onRefreshTap,
                    borderRadius: BorderRadius.circular(16),
                    child: Center(
                      child: Icon(
                        Icons.refresh_rounded,
                        size: 20,
                        color: isDark ? Colors.white70 : Colors.black87,
                      ),
                    ),
                  ),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _MarketplaceGlassBottomBar extends StatelessWidget {
  final int currentPage;
  final bool hasMore;
  final bool isDark;
  final VoidCallback? onPrevTap;
  final VoidCallback? onNextTap;

  const _MarketplaceGlassBottomBar({
    required this.currentPage,
    required this.hasMore,
    required this.isDark,
    required this.onPrevTap,
    required this.onNextTap,
  });

  @override
  Widget build(BuildContext context) {
    final bottomPadding = MediaQuery.of(context).padding.bottom;
    final glassColor = isDark
        ? const Color(0xFF181820).withValues(alpha: 0.90)
        : const Color(0xFFF1F3F5).withValues(alpha: 0.90);

    final border = Border.all(
      color: isDark ? Colors.white.withValues(alpha: 0.12) : Colors.black.withValues(alpha: 0.08),
    );

    return Positioned(
      bottom: bottomPadding + 10,
      left: 16,
      right: 16,
      child: ClipRRect(
        borderRadius: BorderRadius.circular(20),
        child: BackdropFilter(
          filter: ImageFilter.blur(sigmaX: 16, sigmaY: 16),
          child: Container(
            height: 50,
            padding: const EdgeInsets.symmetric(horizontal: 12),
            decoration: BoxDecoration(
              color: glassColor,
              borderRadius: BorderRadius.circular(20),
              border: border,
            ),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Material(
                  color: Colors.transparent,
                  child: InkWell(
                    onTap: onPrevTap,
                    borderRadius: BorderRadius.circular(12),
                    child: Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
                      child: Row(
                        children: [
                          Icon(
                            Icons.arrow_back_ios_rounded,
                            size: 13,
                            color: onPrevTap != null
                                ? (isDark ? Colors.white : Colors.black87)
                                : (isDark ? Colors.white24 : Colors.black26),
                          ),
                          const SizedBox(width: 4),
                          Text(
                            'Previous',
                            style: TextStyle(
                              fontSize: 12,
                              fontWeight: FontWeight.bold,
                              color: onPrevTap != null
                                  ? (isDark ? Colors.white : Colors.black87)
                                  : (isDark ? Colors.white24 : Colors.black26),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                ),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 5),
                  decoration: BoxDecoration(
                    color: isDark ? Colors.white10 : Colors.black.withValues(alpha: 0.06),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: Text(
                    'Page $currentPage',
                    style: TextStyle(
                      fontSize: 12,
                      fontWeight: FontWeight.bold,
                      color: isDark ? Colors.white : Colors.black87,
                    ),
                  ),
                ),
                Material(
                  color: Colors.transparent,
                  child: InkWell(
                    onTap: onNextTap,
                    borderRadius: BorderRadius.circular(12),
                    child: Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
                      child: Row(
                        children: [
                          Text(
                            'Next',
                            style: TextStyle(
                              fontSize: 12,
                              fontWeight: FontWeight.bold,
                              color: onNextTap != null
                                  ? (isDark ? Colors.white : Colors.black87)
                                  : (isDark ? Colors.white24 : Colors.black26),
                            ),
                          ),
                          const SizedBox(width: 4),
                          Icon(
                            Icons.arrow_forward_ios_rounded,
                            size: 13,
                            color: onNextTap != null
                                ? (isDark ? Colors.white : Colors.black87)
                                : (isDark ? Colors.white24 : Colors.black26),
                          ),
                        ],
                      ),
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
