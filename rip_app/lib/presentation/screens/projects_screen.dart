import 'dart:async';
import 'dart:ui';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:rip_app/core/api/rip_client.dart';
import 'package:rip_app/core/api/rip_websocket_client.dart';
import 'package:rip_app/core/design/design.dart';
import 'package:rip_app/data/models/project.dart';
import 'package:rip_app/presentation/providers/connection_provider.dart';
import 'package:rip_app/presentation/providers/project_provider.dart';
import 'package:rip_app/presentation/providers/settings_provider.dart';
import 'package:rip_app/presentation/widgets/common/rip_button.dart';
import 'package:rip_app/presentation/widgets/overlays/first_time_github_onboarding_dialog.dart';
import 'package:rip_app/presentation/widgets/sidebar/app_drawer.dart';

class ProjectsScreen extends ConsumerStatefulWidget {
  const ProjectsScreen({super.key});

  @override
  ConsumerState<ProjectsScreen> createState() => _ProjectsScreenState();
}

class _ProjectsScreenState extends ConsumerState<ProjectsScreen> {
  final _scrollController = ScrollController();
  double _headerT = 0.0;

  bool _isPolling = false;
  int _pollIntervalSeconds = 1;
  Map<String, dynamic>? _activeJobStatus;
  final Map<String, bool> _expandedLogs = {};
  final Set<String> _refreshedCompletedJobIds = {};
  bool _showActiveJobLogs = true;
  final ScrollController _jobLogsScrollController = ScrollController();
  RipWebSocketClient? _wsClient;
  StreamSubscription? _wsSubscription;

  @override
  void initState() {
    super.initState();
    _scrollController.addListener(_handleScroll);
    _isPolling = true;
    _pollLoop();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _initWebSocket();
    });
  }

  @override
  void dispose() {
    _scrollController
      ..removeListener(_handleScroll)
      ..dispose();
    _isPolling = false;
    _wsSubscription?.cancel();
    _wsClient?.dispose();
    _jobLogsScrollController.dispose();
    super.dispose();
  }

  void _handleScroll() {
    if (!_scrollController.hasClients) return;
    final offset = _scrollController.offset;
    final nextHeaderT = (offset / 80).clamp(0.0, 1.0);
    if ((nextHeaderT - _headerT).abs() > 0.02) {
      setState(() => _headerT = nextHeaderT);
    }
  }

  void _initWebSocket() {
    try {
      final baseUrl = ref.read(serverUrlProvider);
      final apiKey = ref.read(apiKeyProvider);
      _wsClient = RipWebSocketClient(serverUrl: baseUrl, apiKey: apiKey);
      _wsClient!.connectJobs();
      _wsSubscription = _wsClient!.stream.listen((data) {
        if (!mounted) return;
        _isPolling = false; // Disable REST polling since WS stream is active
        if (data.containsKey('jobs')) {
          final rawJobs = data['jobs'] as List;
          if (rawJobs.isNotEmpty) {
            final jobs = rawJobs.cast<Map<String, dynamic>>();
            final runningJob = jobs.cast<Map<String, dynamic>?>().firstWhere(
              (j) => j != null && (j['status'] == 'cloning' || j['status'] == 'indexing'),
              orElse: () => null,
            );

            if (runningJob != null) {
              setState(() {
                _activeJobStatus = runningJob;
              });
              if (_jobLogsScrollController.hasClients) {
                _jobLogsScrollController.animateTo(
                  _jobLogsScrollController.position.maxScrollExtent,
                  duration: const Duration(milliseconds: 150),
                  curve: Curves.easeOut,
                );
              }
            } else {
              for (final j in jobs) {
                final jobId = j['job_id'] as String? ?? j['project_name'] as String? ?? '';
                final status = (j['status'] as String? ?? '').toLowerCase();
                if (status == 'complete' && jobId.isNotEmpty) {
                  if (!_refreshedCompletedJobIds.contains(jobId)) {
                    _refreshedCompletedJobIds.add(jobId);
                    ref.invalidate(projectListProvider);
                  }
                }
              }
              if (_activeJobStatus != null && (_activeJobStatus!['status'] as String? ?? '').toLowerCase() != 'failed') {
                setState(() {
                  _activeJobStatus = null;
                });
              }
            }
          }
        }
      });
    } catch (_) {
      // Fallback to polling loop
    }
  }

  Future<void> _pollLoop() async {
    while (_isPolling && mounted) {
      await _fetchJobStatus();
      if (!_isPolling || !mounted) break;
      await Future.delayed(Duration(seconds: _pollIntervalSeconds));
    }
  }

  Future<void> _fetchJobStatus() async {
    try {
      final client = ref.read(ripClientProvider);
      final jobs = await client.listGitJobs();
      if (mounted) {
        if (jobs.isNotEmpty) {
          final runningJob = jobs.cast<Map<String, dynamic>?>().firstWhere(
            (j) => j != null && (j['status'] == 'cloning' || j['status'] == 'indexing'),
            orElse: () => null,
          );

          if (runningJob != null) {
            setState(() {
              _activeJobStatus = runningJob;
            });
            if (_jobLogsScrollController.hasClients) {
              _jobLogsScrollController.animateTo(
                _jobLogsScrollController.position.maxScrollExtent,
                duration: const Duration(milliseconds: 200),
                curve: Curves.easeOut,
              );
            }
            _pollIntervalSeconds = 1;
          } else {
            for (final j in jobs) {
              final jobId = j['job_id'] as String? ?? j['project_name'] as String? ?? '';
              final status = (j['status'] as String? ?? '').toLowerCase();
              if (status == 'complete' && jobId.isNotEmpty) {
                if (!_refreshedCompletedJobIds.contains(jobId)) {
                  _refreshedCompletedJobIds.add(jobId);
                  ref.invalidate(projectListProvider);
                }
              }
            }
            if (_activeJobStatus != null && (_activeJobStatus!['status'] as String? ?? '').toLowerCase() != 'failed') {
              setState(() {
                _activeJobStatus = null;
              });
            }
            _isPolling = false;
          }
        } else {
          _isPolling = false;
          setState(() {
            _activeJobStatus = null;
          });
        }
      }
    } catch (_) {
      _isPolling = false;
    }
  }

  Future<void> _confirmDeleteProject(
    BuildContext context,
    WidgetRef ref,
    String projectId,
    String projectName,
  ) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: const Color(0xFF14141A),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
        title: Text('Delete $projectName?', style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
        content: const Text(
          'This will permanently delete this project, including its Neo4j AST graph nodes, Qdrant vector embeddings, database memories, and cloned folder in .remote-repos.',
          style: TextStyle(color: Colors.white70, fontSize: 13),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(false),
            child: const Text('Cancel', style: TextStyle(color: Colors.white60)),
          ),
          ElevatedButton(
            onPressed: () => Navigator.of(ctx).pop(true),
            style: ElevatedButton.styleFrom(
              backgroundColor: const Color(0xFFEF4444),
              foregroundColor: Colors.white,
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
            ),
            child: const Text('Delete', style: TextStyle(fontWeight: FontWeight.bold)),
          ),
        ],
      ),
    );

    if (confirmed == true && context.mounted) {
      try {
        final activeId = ref.read(activeProjectIdProvider);
        if (activeId == projectId) {
          await ref.read(activeProjectNotifierProvider.notifier).setActiveProject(null);
        }
        final client = ref.read(ripClientProvider);
        await client.deleteProject(projectId);
        ref.invalidate(projectListProvider);
        if (context.mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text('Project "$projectName" deleted'),
              backgroundColor: const Color(0xFF22C55E),
            ),
          );
        }
      } catch (e) {
        if (context.mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text('Failed to delete project: $e'),
              backgroundColor: const Color(0xFFEF4444),
            ),
          );
        }
      }
    }
  }

  void _openIndexOnboardingDialog() {
    HapticFeedback.mediumImpact();
    showDialog(
      context: context,
      builder: (context) => const FirstTimeGithubOnboardingDialog(),
    ).then((_) {
      if (mounted && !_isPolling) {
        _isPolling = true;
        _pollLoop();
      }
      ref.invalidate(projectListProvider);
    });
  }

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final bgColor = isDark ? const Color(0xFF0D0D12) : const Color(0xFFF8F9FA);
    final topPadding = MediaQuery.of(context).padding.top;
    final bottomPadding = MediaQuery.of(context).padding.bottom;

    final projectsAsync = ref.watch(projectListProvider);
    final activeProjectId = ref.watch(activeProjectIdProvider);
    final projectsList = projectsAsync.asData?.value ?? [];

    return Scaffold(
      extendBodyBehindAppBar: true,
      drawer: const AppDrawer(),
      drawerEdgeDragWidth: MediaQuery.sizeOf(context).width * 0.4,
      backgroundColor: bgColor,
      body: Stack(
        children: [
          // 1. Background Base Color
          ColoredBox(color: bgColor),

          // 2. Infinite Scrollable Content Area (Single Body Layout)
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
                // A. LIVE BACKGROUND JOB TELEMETRY CARD (WS Stream Push)
                if (_activeJobStatus != null) ...[
                  _SectionLabel(title: 'LIVE CLONE & INDEXING TELEMETRY', isDark: isDark),
                  const SizedBox(height: 10),
                  _buildActiveJobCard(isDark),
                  const SizedBox(height: 20),
                ],

                // B. INDEXED WORKSPACES SECTION
                _SectionLabel(title: 'INDEXED REPOSITORIES & WORKSPACES', isDark: isDark),
                const SizedBox(height: 10),

                if (projectsAsync.isLoading)
                  const SizedBox(
                    height: 140,
                    child: Center(child: CircularProgressIndicator(strokeWidth: 2)),
                  )
                else if (projectsAsync.hasError)
                  Container(
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(
                      color: const Color(0xFFEF4444).withValues(alpha: 0.1),
                      borderRadius: BorderRadius.circular(16),
                    ),
                    child: Text(
                      'Error loading repositories: ${projectsAsync.error}',
                      style: const TextStyle(color: Color(0xFFEF4444), fontSize: 13),
                    ),
                  )
                else if (projectsList.isEmpty)
                  _buildEmptyProjectsState(context, isDark)
                else
                  ...projectsList.map((p) {
                    final pId = p.projectId;
                    final isActive = pId == activeProjectId;
                    final showLogs = _expandedLogs[pId] ?? false;

                    return _buildProjectCard(context, p, isActive, showLogs, isDark);
                  }),

                const SizedBox(height: 24),
              ],
            ),
          ),

          // 3. TOP FADE GRADIENT OVERLAY (Linear gradient header transition)
          Positioned(
            top: 0,
            left: 0,
            right: 0,
            height: topPadding + 110,
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
                    stops: const [0.0, 0.55, 1.0],
                  ),
                ),
              ),
            ),
          ),

          // 4. BOTTOM FADE GRADIENT OVERLAY (Linear gradient footer transition)
          Positioned(
            bottom: 0,
            left: 0,
            right: 0,
            height: bottomPadding + 70,
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
                    stops: const [0.0, 0.55, 1.0],
                  ),
                ),
              ),
            ),
          ),

          // 5. SEPARATED FLOATING GLASSMORPHIC TOP BAR COMPONENTS
          _ProjectsGlassHeader(
            progress: _headerT,
            isDark: isDark,
            projectCount: projectsList.length,
            onBackTap: () {
              HapticFeedback.selectionClick();
              if (context.canPop()) {
                context.pop();
              } else {
                Scaffold.of(context).openDrawer();
              }
            },
            onIndexTap: _openIndexOnboardingDialog,
          ),
        ],
      ),
    );
  }



  Widget _buildEmptyProjectsState(BuildContext context, bool isDark) {
    final cardBgColor = isDark ? const Color(0xFF14141A) : Colors.white;
    final textColor = isDark ? Colors.white : AppColors.textPrimary;
    final mutedColor = isDark ? Colors.white54 : AppColors.textSecondary;

    return Container(
      padding: const EdgeInsets.symmetric(vertical: 36, horizontal: 20),
      decoration: BoxDecoration(
        color: cardBgColor,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(
          color: isDark
              ? Colors.white.withValues(alpha: 0.08)
              : Colors.black.withValues(alpha: 0.06),
        ),
      ),
      child: Center(
        child: Column(
          children: [
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: isDark ? Colors.white.withValues(alpha: 0.05) : Colors.black.withValues(alpha: 0.04),
                shape: BoxShape.circle,
              ),
              child: Icon(Icons.folder_open_rounded, size: 36, color: mutedColor),
            ),
            const SizedBox(height: 14),
            Text(
              'No Indexed Repositories Yet',
              style: TextStyle(fontSize: 15, fontWeight: FontWeight.bold, color: textColor),
            ),
            const SizedBox(height: 6),
            Text(
              'Tap "+ Index Repo" to clone a GitHub repo into Neo4j graph & Qdrant vector memory',
              textAlign: TextAlign.center,
              style: TextStyle(fontSize: 12, color: mutedColor),
            ),
            const SizedBox(height: 18),
            RipButton.primary(
              label: 'Index GitHub Repo',
              icon: const Icon(Icons.add_rounded, size: 16),
              onPressed: _openIndexOnboardingDialog,
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildProjectCard(
    BuildContext context,
    Project p,
    bool isActive,
    bool showLogs,
    bool isDark,
  ) {
    final cardBgColor = isDark ? const Color(0xFF14141A) : Colors.white;
    final textColor = isDark ? Colors.white : AppColors.textPrimary;
    final mutedColor = isDark ? Colors.white54 : AppColors.textSecondary;
    final border = Border.all(
      color: isActive
          ? AppColors.primary
          : (isDark ? Colors.white.withValues(alpha: 0.08) : Colors.black.withValues(alpha: 0.06)),
      width: isActive ? 1.5 : 1.0,
    );

    final pId = p.projectId;

    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      decoration: BoxDecoration(
        color: cardBgColor,
        borderRadius: BorderRadius.circular(18),
        border: border,
        boxShadow: isActive
            ? [
                BoxShadow(
                  color: AppColors.primary.withValues(alpha: 0.12),
                  blurRadius: 12,
                  offset: const Offset(0, 4),
                ),
              ]
            : null,
      ),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            InkWell(
              onTap: () {
                HapticFeedback.selectionClick();
                context.push('/projects/$pId');
              },
              borderRadius: BorderRadius.circular(14),
              child: Padding(
                padding: const EdgeInsets.symmetric(vertical: 4),
                child: Row(
                  children: [
                    Container(
                      padding: const EdgeInsets.all(10),
                      decoration: BoxDecoration(
                        color: isActive
                            ? AppColors.primary.withValues(alpha: 0.15)
                            : (isDark ? const Color(0xFF22222E) : const Color(0xFFEFEFF5)),
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: Icon(
                        Icons.folder_rounded,
                        color: isActive ? AppColors.primary : (isDark ? Colors.white70 : Colors.black87),
                        size: 20,
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            children: [
                              Flexible(
                                child: Text(
                                  p.projectName,
                                  style: TextStyle(
                                    fontWeight: FontWeight.bold,
                                    fontSize: 15,
                                    color: textColor,
                                    letterSpacing: -0.2,
                                  ),
                                  maxLines: 1,
                                  overflow: TextOverflow.ellipsis,
                                ),
                              ),
                              if (isActive) ...[
                                const SizedBox(width: 6),
                                Container(
                                  padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                                  decoration: BoxDecoration(
                                    color: const Color(0xFF22C55E).withValues(alpha: 0.15),
                                    borderRadius: BorderRadius.circular(6),
                                  ),
                                  child: const Text(
                                    'ACTIVE',
                                    style: TextStyle(fontSize: 9, fontWeight: FontWeight.bold, color: Color(0xFF22C55E)),
                                  ),
                                ),
                              ],
                            ],
                          ),
                          const SizedBox(height: 2),
                          Text(
                            p.locationLabel,
                            style: TextStyle(fontSize: 11.5, color: mutedColor),
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                          ),
                        ],
                      ),
                    ),
                    Icon(Icons.chevron_right_rounded, size: 20, color: mutedColor),
                    const SizedBox(width: 4),
                    IconButton(
                      onPressed: () => _confirmDeleteProject(context, ref, pId, p.projectName),
                      icon: const Icon(Icons.delete_outline_rounded, size: 18, color: Color(0xFFEF4444)),
                      tooltip: 'Delete Project',
                      visualDensity: VisualDensity.compact,
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 12),
            Wrap(
              spacing: 8,
              runSpacing: 6,
              children: [
                _StatBadge(icon: Icons.insert_drive_file_outlined, label: '${p.filesCount} Files', isDark: isDark),
                _StatBadge(icon: Icons.hub_outlined, label: '${p.entitiesCount} Entities', isDark: isDark),
                _StatBadge(icon: Icons.account_tree_outlined, label: 'Neo4j AST Graph', isDark: isDark),
                _StatBadge(icon: Icons.memory_outlined, label: 'Qdrant Vectors', isDark: isDark),
              ],
            ),
            const SizedBox(height: 12),
            Divider(height: 1, color: isDark ? Colors.white10 : Colors.black.withValues(alpha: 0.06)),
            const SizedBox(height: 10),
            Row(
              children: [
                TextButton.icon(
                  onPressed: () {
                    HapticFeedback.selectionClick();
                    setState(() {
                      _expandedLogs[pId] = !showLogs;
                    });
                  },
                  icon: Icon(showLogs ? Icons.terminal : Icons.terminal_outlined, size: 14, color: mutedColor),
                  label: Text(
                    showLogs ? 'Hide CLI Logs' : 'View CLI Logs',
                    style: TextStyle(fontSize: 11, color: mutedColor),
                  ),
                  style: TextButton.styleFrom(visualDensity: VisualDensity.compact),
                ),
                const Spacer(),
                OutlinedButton.icon(
                  onPressed: () {
                    HapticFeedback.selectionClick();
                    context.push('/projects/$pId');
                  },
                  icon: const Icon(Icons.analytics_outlined, size: 13),
                  label: const Text('Insights', style: TextStyle(fontSize: 11)),
                  style: OutlinedButton.styleFrom(
                    visualDensity: VisualDensity.compact,
                    side: BorderSide(color: isDark ? Colors.white24 : Colors.black26),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 6),
                    foregroundColor: textColor,
                  ),
                ),
                const SizedBox(width: 6),
                if (!isActive)
                  OutlinedButton(
                    onPressed: () async {
                      HapticFeedback.selectionClick();
                      await ref.read(activeProjectNotifierProvider.notifier).setActiveProject(pId);
                      ref.invalidate(projectListProvider);
                    },
                    style: OutlinedButton.styleFrom(
                      visualDensity: VisualDensity.compact,
                      side: BorderSide(color: isDark ? Colors.white24 : Colors.black26),
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 6),
                    ),
                    child: Text('Set Active', style: TextStyle(fontSize: 11, color: textColor)),
                  ),
                const SizedBox(width: 6),
                ElevatedButton(
                  onPressed: () {
                    HapticFeedback.selectionClick();
                    context.push('/sandbox/$pId');
                  },
                  style: ElevatedButton.styleFrom(
                    backgroundColor: isDark ? const Color(0xFF22222E) : Colors.black,
                    foregroundColor: Colors.white,
                    visualDensity: VisualDensity.compact,
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                  ),
                  child: const Text('Sandbox', style: TextStyle(fontSize: 11, fontWeight: FontWeight.bold)),
                ),
              ],
            ),
            if (showLogs) ...[
              const SizedBox(height: 10),
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: const Color(0xFF09090D),
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: Colors.white10),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        const Icon(Icons.circle, size: 8, color: Color(0xFF22C55E)),
                        const SizedBox(width: 6),
                        const Text(
                          'CLI Indexing Telemetry Logs',
                          style: TextStyle(
                            fontSize: 10,
                            fontWeight: FontWeight.bold,
                            color: Colors.white70,
                            fontFamily: 'monospace',
                          ),
                        ),
                        const Spacer(),
                        Text(
                          'Real-time',
                          style: TextStyle(fontSize: 9, color: Colors.white38, fontFamily: 'monospace'),
                        ),
                      ],
                    ),
                    const Divider(height: 12, color: Colors.white10),
                    ...(_activeJobStatus?['logs'] as List? ?? [
                      '[00:00:00] 📂 Discovered repository files',
                      '[00:00:01] ⚡ Parsed files via Tree-Sitter AST parser',
                      '[00:00:02] 🕸️ Generated Neo4j Knowledge Call Graph',
                      '[00:00:03] 🧬 Indexed Qdrant Vector Embeddings',
                      '[00:00:04] 📜 Ingested Git Commit & Author history',
                      '[00:00:05] 🗃️ Persisted Workspace & Execution Memory',
                      '[00:00:06] ✅ Project successfully indexed into RIP DB',
                    ]).map(
                      (log) => Padding(
                        padding: const EdgeInsets.symmetric(vertical: 2),
                        child: Text(
                          log.toString(),
                          style: const TextStyle(
                            fontSize: 10.5,
                            color: Color(0xFF38BDF8),
                            fontFamily: 'monospace',
                          ),
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildActiveJobCard(bool isDark) {
    if (_activeJobStatus == null) return const SizedBox.shrink();

    final status = (_activeJobStatus!['status'] as String? ?? 'pending').toLowerCase();
    if (status == 'complete') return const SizedBox.shrink();

    final isRunning = status == 'cloning' || status == 'indexing';
    final isComplete = status == 'complete';
    final isFailed = status == 'failed';
    final projectName = _activeJobStatus!['project_name'] ?? 'Repository';
    final filesIndexed = _activeJobStatus!['files_indexed'] ?? 0;
    final entitiesFound = _activeJobStatus!['entities_found'] ?? 0;
    final rawLogs = (_activeJobStatus!['logs'] as List? ?? []).map((e) => e.toString()).toList();

    final statusColor = isFailed
        ? const Color(0xFFEF4444)
        : (isComplete ? const Color(0xFF22C55E) : const Color(0xFF38BDF8));

    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: statusColor.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: statusColor.withValues(alpha: 0.3)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              if (isRunning)
                SizedBox(
                  width: 14,
                  height: 14,
                  child: CircularProgressIndicator(strokeWidth: 2, color: statusColor),
                )
              else
                Icon(
                  isComplete ? Icons.check_circle_rounded : Icons.error_rounded,
                  size: 16,
                  color: statusColor,
                ),
              const SizedBox(width: 10),
              Expanded(
                child: Text(
                  isRunning
                      ? 'Indexing "$projectName" in background...'
                      : (isComplete ? '"$projectName" indexing complete!' : 'Indexing "$projectName" failed'),
                  style: TextStyle(fontWeight: FontWeight.bold, fontSize: 13, color: statusColor),
                ),
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                decoration: BoxDecoration(
                  color: statusColor.withValues(alpha: 0.2),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Text(
                  status.toUpperCase(),
                  style: TextStyle(fontSize: 10, fontWeight: FontWeight.bold, color: statusColor),
                ),
              ),
              const SizedBox(width: 4),
              IconButton(
                onPressed: () {
                  setState(() {
                    _activeJobStatus = null;
                  });
                },
                icon: const Icon(Icons.close_rounded, size: 16, color: Colors.white54),
                tooltip: 'Dismiss Telemetry Banner',
                visualDensity: VisualDensity.compact,
              ),
            ],
          ),
          const SizedBox(height: 8),
          Text(
            _activeJobStatus!['progress_message'] ?? 'Processing pipeline...',
            style: TextStyle(fontSize: 11, color: isDark ? Colors.white70 : AppColors.textSecondary),
          ),
          const SizedBox(height: 8),
          ClipRRect(
            borderRadius: BorderRadius.circular(4),
            child: LinearProgressIndicator(
              value: isComplete ? 1.0 : (status == 'indexing' ? 0.75 : 0.25),
              minHeight: 4,
              backgroundColor: Colors.white10,
              color: statusColor,
            ),
          ),
          const SizedBox(height: 10),
          Wrap(
            spacing: 8,
            runSpacing: 6,
            children: [
              _StatBadge(icon: Icons.insert_drive_file_outlined, label: '$filesIndexed Files', isDark: isDark),
              _StatBadge(icon: Icons.hub_outlined, label: '$entitiesFound Neo4j AST Entities', isDark: isDark),
              _StatBadge(icon: Icons.memory_outlined, label: '$entitiesFound Qdrant Embeddings', isDark: isDark),
            ],
          ),
          const SizedBox(height: 8),
          Row(
            children: [
              TextButton.icon(
                onPressed: () {
                  setState(() {
                    _showActiveJobLogs = !_showActiveJobLogs;
                  });
                },
                icon: Icon(
                  _showActiveJobLogs ? Icons.terminal : Icons.terminal_outlined,
                  size: 14,
                  color: statusColor,
                ),
                label: Text(
                  _showActiveJobLogs
                      ? 'Hide CLI Logs'
                      : 'View CLI Live Stream (${rawLogs.length} lines)',
                  style: TextStyle(fontSize: 11, fontWeight: FontWeight.w600, color: statusColor),
                ),
                style: TextButton.styleFrom(visualDensity: VisualDensity.compact),
              ),
            ],
          ),
          if (_showActiveJobLogs && rawLogs.isNotEmpty) ...[
            const SizedBox(height: 6),
            Container(
              height: 180,
              width: double.infinity,
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: const Color(0xFF08090C),
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: statusColor.withValues(alpha: 0.2)),
              ),
              child: ListView.builder(
                controller: _jobLogsScrollController,
                itemCount: rawLogs.length,
                itemBuilder: (context, idx) {
                  final line = rawLogs[idx];
                  return Padding(
                    padding: const EdgeInsets.symmetric(vertical: 2),
                    child: Text(
                      line,
                      style: TextStyle(
                        fontSize: 10.5,
                        fontFamily: 'monospace',
                        height: 1.3,
                        color: line.contains('✅') || line.contains('Complete')
                            ? const Color(0xFF22C55E)
                            : (line.contains('❌') || line.contains('failed')
                                ? const Color(0xFFEF4444)
                                : (line.contains('⚡') || line.contains('Step')
                                    ? const Color(0xFFF59E0B)
                                    : const Color(0xFF38BDF8))),
                      ),
                    ),
                  );
                },
              ),
            ),
          ],
        ],
      ),
    );
  }
}

class _ProjectsGlassHeader extends StatelessWidget {
  const _ProjectsGlassHeader({
    required this.progress,
    required this.isDark,
    required this.onBackTap,
    required this.onIndexTap,
    required this.projectCount,
  });

  final double progress;
  final bool isDark;
  final VoidCallback onBackTap;
  final VoidCallback onIndexTap;
  final int projectCount;

  @override
  Widget build(BuildContext context) {
    final topPadding = MediaQuery.of(context).padding.top;
    final glassColor = isDark
        ? Color.lerp(const Color(0xFF14141A).withValues(alpha: 0.65), const Color(0xFF14141A).withValues(alpha: 0.92), progress)!
        : Color.lerp(Colors.white.withValues(alpha: 0.70), Colors.white.withValues(alpha: 0.95), progress)!;
    final border = Border.all(
      color: isDark ? Colors.white.withValues(alpha: 0.12) : Colors.black.withValues(alpha: 0.08),
    );

    final canPop = context.canPop();

    return Positioned(
      top: topPadding + 8,
      left: 16,
      right: 16,
      child: Row(
        children: [
          // 1. SEPARATE FLOATING GLASS COMPONENT: Back / Drawer Menu Button
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
                        canPop ? Icons.arrow_back_rounded : Icons.menu_rounded,
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

          // 2. SEPARATE FLOATING GLASS COMPONENT: Header Title Pill
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
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Container(
                      width: 7,
                      height: 7,
                      decoration: const BoxDecoration(
                        color: Color(0xFF22C55E),
                        shape: BoxShape.circle,
                      ),
                    ),
                    const SizedBox(width: 8),
                    Text(
                      'Workspaces',
                      style: TextStyle(
                        fontSize: 14,
                        fontWeight: FontWeight.bold,
                        color: isDark ? Colors.white : Colors.black87,
                      ),
                    ),
                    const SizedBox(width: 8),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                      decoration: BoxDecoration(
                        color: isDark ? Colors.white10 : Colors.black.withValues(alpha: 0.05),
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: Text(
                        '$projectCount',
                        style: TextStyle(
                          fontSize: 10.5,
                          fontWeight: FontWeight.bold,
                          color: isDark ? Colors.white70 : AppColors.textSecondary,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
          const Spacer(),

          // 3. SEPARATE FLOATING GLASS COMPONENT: Index Repo Button
          ClipRRect(
            borderRadius: BorderRadius.circular(16),
            child: BackdropFilter(
              filter: ImageFilter.blur(sigmaX: 16, sigmaY: 16),
              child: Container(
                height: 44,
                decoration: BoxDecoration(
                  color: glassColor,
                  borderRadius: BorderRadius.circular(16),
                  border: border,
                ),
                child: Material(
                  color: Colors.transparent,
                  child: InkWell(
                    onTap: onIndexTap,
                    borderRadius: BorderRadius.circular(16),
                    child: Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 14),
                      child: Row(
                        children: [
                          Icon(
                            Icons.add_rounded,
                            size: 18,
                            color: isDark ? Colors.white : AppColors.primary,
                          ),
                          const SizedBox(width: 6),
                          Text(
                            'Index Repo',
                            style: TextStyle(
                              fontSize: 12.5,
                              fontWeight: FontWeight.bold,
                              color: isDark ? Colors.white : AppColors.textPrimary,
                            ),
                          ),
                        ],
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

class _HeroStatTile extends StatelessWidget {
  const _HeroStatTile({
    required this.title,
    required this.value,
    required this.icon,
    required this.isDark,
  });

  final String title;
  final String value;
  final IconData icon;
  final bool isDark;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: BoxDecoration(
        color: isDark ? Colors.white.withValues(alpha: 0.04) : Colors.black.withValues(alpha: 0.03),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: isDark ? Colors.white.withValues(alpha: 0.06) : Colors.black.withValues(alpha: 0.05),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(icon, size: 13, color: isDark ? Colors.white60 : AppColors.textSecondary),
              const SizedBox(width: 4),
              Expanded(
                child: Text(
                  title,
                  style: TextStyle(
                    fontSize: 10,
                    fontWeight: FontWeight.w600,
                    color: isDark ? Colors.white60 : AppColors.textSecondary,
                  ),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
              ),
            ],
          ),
          const SizedBox(height: 4),
          Text(
            value,
            style: TextStyle(
              fontSize: 15,
              fontWeight: FontWeight.bold,
              color: isDark ? Colors.white : AppColors.textPrimary,
            ),
          ),
        ],
      ),
    );
  }
}

class _SectionLabel extends StatelessWidget {
  const _SectionLabel({required this.title, required this.isDark});

  final String title;
  final bool isDark;

  @override
  Widget build(BuildContext context) {
    return Text(
      title,
      style: TextStyle(
        fontSize: 11,
        fontWeight: FontWeight.bold,
        letterSpacing: 1.1,
        color: isDark ? Colors.white38 : AppColors.textSecondary,
      ),
    );
  }
}

class _StatBadge extends StatelessWidget {
  const _StatBadge({
    required this.icon,
    required this.label,
    required this.isDark,
  });

  final IconData icon;
  final String label;
  final bool isDark;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: isDark
            ? Colors.white.withValues(alpha: 0.06)
            : Colors.black.withValues(alpha: 0.04),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(
          color: isDark
              ? Colors.white.withValues(alpha: 0.08)
              : Colors.black.withValues(alpha: 0.06),
        ),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 12, color: isDark ? Colors.white70 : AppColors.textSecondary),
          const SizedBox(width: 5),
          Text(
            label,
            style: TextStyle(
              fontSize: 10.5,
              fontWeight: FontWeight.w600,
              color: isDark ? Colors.white70 : AppColors.textSecondary,
            ),
          ),
        ],
      ),
    );
  }
}
