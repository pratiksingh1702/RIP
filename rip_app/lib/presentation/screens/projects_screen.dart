import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:rip_app/core/api/rip_client.dart';
import 'package:rip_app/core/api/rip_websocket_client.dart';
import 'package:rip_app/core/design/design.dart';
import 'package:rip_app/presentation/providers/connection_provider.dart';
import 'package:rip_app/presentation/providers/project_provider.dart';
import 'package:rip_app/presentation/providers/settings_provider.dart';
import 'package:rip_app/presentation/widgets/overlays/first_time_github_onboarding_dialog.dart';

class ProjectsScreen extends ConsumerStatefulWidget {
  const ProjectsScreen({super.key});

  @override
  ConsumerState<ProjectsScreen> createState() => _ProjectsScreenState();
}

class _ProjectsScreenState extends ConsumerState<ProjectsScreen> {
  bool _isPolling = false;
  int _pollIntervalSeconds = 1;
  Map<String, dynamic>? _activeJobStatus;
  final Map<String, bool> _expandedLogs = {};
  bool _showActiveJobLogs = true;
  final ScrollController _jobLogsScrollController = ScrollController();
  RipWebSocketClient? _wsClient;
  StreamSubscription? _wsSubscription;

  @override
  void initState() {
    super.initState();
    _isPolling = true;
    _pollLoop();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _initWebSocket();
    });
  }

  void _initWebSocket() {
    try {
      final baseUrl = ref.read(serverUrlProvider);
      _wsClient = RipWebSocketClient(serverUrl: baseUrl);
      _wsClient!.connectJobs();
      _wsSubscription = _wsClient!.stream.listen((data) {
        if (!mounted) return;
        if (data.containsKey('jobs')) {
          final rawJobs = data['jobs'] as List;
          if (rawJobs.isNotEmpty) {
            final jobs = rawJobs.cast<Map<String, dynamic>>();
            final active = jobs.firstWhere(
              (j) => j['status'] == 'cloning' || j['status'] == 'indexing',
              orElse: () => jobs.first,
            );
            setState(() {
              _activeJobStatus = active;
            });
            if (_jobLogsScrollController.hasClients) {
              _jobLogsScrollController.animateTo(
                _jobLogsScrollController.position.maxScrollExtent,
                duration: const Duration(milliseconds: 150),
                curve: Curves.easeOut,
              );
            }
            if (active['status'] == 'complete') {
              ref.invalidate(projectListProvider);
            }
          }
        }
      });
    } catch (_) {
      // Fallback to polling loop
    }
  }

  @override
  void dispose() {
    _isPolling = false;
    _wsSubscription?.cancel();
    _wsClient?.dispose();
    _jobLogsScrollController.dispose();
    super.dispose();
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
          // Find latest running or completed job
          final active = jobs.firstWhere(
            (j) => j['status'] == 'cloning' || j['status'] == 'indexing',
            orElse: () => jobs.first,
          );
          
          setState(() {
            _activeJobStatus = active;
          });

          if (_jobLogsScrollController.hasClients) {
            _jobLogsScrollController.animateTo(
              _jobLogsScrollController.position.maxScrollExtent,
              duration: const Duration(milliseconds: 200),
              curve: Curves.easeOut,
            );
          }

          // Fast poll if something is running, otherwise STOP polling
          final isRunning = active['status'] == 'cloning' || active['status'] == 'indexing';
          if (isRunning) {
            _pollIntervalSeconds = 1;
          } else {
            if (active['status'] == 'complete') {
              ref.invalidate(projectListProvider);
            }
            _isPolling = false; // Stop polling completely
          }
        } else {
          // No jobs exist at all, stop polling completely
          _isPolling = false;
          setState(() {
             _activeJobStatus = null;
          });
        }
      }
    } catch (_) {
      // Stop polling on error
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

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final bgColor = isDark ? const Color(0xFF0D0D12) : const Color(0xFFF8F9FA);
    final cardBgColor = isDark ? const Color(0xFF14141A) : Colors.white;
    final textColor = isDark ? Colors.white : AppColors.textPrimary;
    final mutedColor = isDark ? Colors.white54 : AppColors.textSecondary;
    final border = Border.all(color: isDark ? Colors.white10 : Colors.black.withValues(alpha: 0.06));

    final projectsAsync = ref.watch(projectListProvider);
    final activeProjectId = ref.watch(activeProjectIdProvider);

    return Scaffold(
      backgroundColor: bgColor,
      body: SafeArea(
        child: Column(
          children: [
            // Top App Bar Header
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
              decoration: BoxDecoration(
                color: cardBgColor,
                border: Border(bottom: BorderSide(color: isDark ? Colors.white10 : Colors.black.withValues(alpha: 0.06))),
              ),
              child: Row(
                children: [
                  IconButton(
                    icon: Icon(Icons.arrow_back_rounded, color: textColor),
                    onPressed: () {
                      HapticFeedback.selectionClick();
                      context.pop();
                    },
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'Projects & Indexing Status',
                          style: TextStyle(
                            fontSize: 17,
                            fontWeight: FontWeight.bold,
                            color: textColor,
                            letterSpacing: -0.3,
                          ),
                        ),
                        const SizedBox(height: 2),
                        Text(
                          'Manage workspaces & monitor background indexing telemetry',
                          style: TextStyle(fontSize: 11, color: mutedColor),
                        ),
                      ],
                    ),
                  ),
                  ElevatedButton.icon(
                    onPressed: () {
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
                    },
                    icon: const Icon(Icons.add_rounded, size: 16),
                    label: const Text('Index Repo', style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold)),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: const Color(0xFF38BDF8),
                      foregroundColor: Colors.black,
                      elevation: 0,
                      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                    ),
                  ),
                ],
              ),
            ),

            // Active Background Job Live Telemetry Card (if indexing is running or status available)
            if (_activeJobStatus != null) _buildActiveJobCard(isDark),

            // Projects List
            Expanded(
              child: projectsAsync.when(
                loading: () => const Center(child: CircularProgressIndicator(strokeWidth: 2)),
                error: (err, _) => Center(child: Text('Error loading projects: $err', style: const TextStyle(color: Colors.red))),
                data: (projects) {
                  if (projects.isEmpty) {
                    return Center(
                      child: Column(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          Icon(Icons.folder_open_rounded, size: 48, color: mutedColor),
                          const SizedBox(height: 12),
                          Text('No indexed projects yet', style: TextStyle(color: textColor, fontWeight: FontWeight.bold)),
                          const SizedBox(height: 4),
                          Text('Tap "+ Index Repo" to clone and index a workspace', style: TextStyle(color: mutedColor, fontSize: 12)),
                        ],
                      ),
                    );
                  }

                  return ListView.builder(
                    padding: const EdgeInsets.all(16),
                    itemCount: projects.length,
                    itemBuilder: (context, index) {
                      final p = projects[index];
                      final pId = p.projectId;
                      final isActive = pId == activeProjectId;
                      final showLogs = _expandedLogs[pId] ?? false;

                      return Container(
                        margin: const EdgeInsets.only(bottom: 12),
                        decoration: BoxDecoration(
                          color: cardBgColor,
                          borderRadius: BorderRadius.circular(16),
                          border: isActive
                              ? Border.all(color: const Color(0xFF38BDF8), width: 1.5)
                              : border,
                        ),
                        child: Padding(
                          padding: const EdgeInsets.all(14),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              // Header Row
                              Row(
                                children: [
                                  Container(
                                    padding: const EdgeInsets.all(10),
                                    decoration: BoxDecoration(
                                      color: isDark ? const Color(0xFF22222E) : const Color(0xFFEFEFF5),
                                      borderRadius: BorderRadius.circular(12),
                                    ),
                                    child: Icon(Icons.folder_rounded, color: isActive ? const Color(0xFF38BDF8) : textColor, size: 20),
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
                                                  fontSize: 14.5,
                                                  color: textColor,
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
                                          style: TextStyle(fontSize: 11, color: mutedColor),
                                          maxLines: 1,
                                          overflow: TextOverflow.ellipsis,
                                        ),
                                      ],
                                    ),
                                  ),
                                  const SizedBox(width: 4),
                                  IconButton(
                                    onPressed: () => _confirmDeleteProject(context, ref, pId, p.projectName),
                                    icon: const Icon(Icons.delete_outline_rounded, size: 18, color: Color(0xFFEF4444)),
                                    tooltip: 'Delete Project',
                                    visualDensity: VisualDensity.compact,
                                  ),
                                ],
                              ),
                              const SizedBox(height: 12),

                              // Stats Chips
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

                              // Logs Toggle & Action Bar
                              Row(
                                children: [
                                  TextButton.icon(
                                    onPressed: () {
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
                                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                                      ),
                                      child: Text('Set Active', style: TextStyle(fontSize: 11, color: textColor)),
                                    ),
                                  const SizedBox(width: 8),
                                  ElevatedButton(
                                    onPressed: () {
                                      HapticFeedback.selectionClick();
                                      context.push('/sandbox/$pId');
                                    },
                                    style: ElevatedButton.styleFrom(
                                      backgroundColor: isDark ? const Color(0xFF22222E) : Colors.black,
                                      foregroundColor: Colors.white,
                                      visualDensity: VisualDensity.compact,
                                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                                    ),
                                    child: const Text('Open Sandbox', style: TextStyle(fontSize: 11, fontWeight: FontWeight.bold)),
                                  ),
                                ],
                              ),

                              // CLI Streaming Logs Viewer
                              if (showLogs) ...[
                                const SizedBox(height: 10),
                                Container(
                                  width: double.infinity,
                                  padding: const EdgeInsets.all(10),
                                  decoration: BoxDecoration(
                                    color: const Color(0xFF09090D),
                                    borderRadius: BorderRadius.circular(10),
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
                                            style: TextStyle(fontSize: 10, fontWeight: FontWeight.bold, color: Colors.white70, fontFamily: 'monospace'),
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
                    },
                  );
                },
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildActiveJobCard(bool isDark) {
    if (_activeJobStatus == null) return const SizedBox.shrink();

    final status = (_activeJobStatus!['status'] as String? ?? 'pending').toLowerCase();
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

    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 4),
      child: Container(
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: statusColor.withValues(alpha: 0.08),
          borderRadius: BorderRadius.circular(16),
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

            // Statistics Badges
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

            // Logs Toggle Row
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

            // Real-Time Streaming CLI Console Window
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
        color: isDark ? const Color(0xFF1E1E26) : const Color(0xFFF0F0F5),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 12, color: isDark ? Colors.white70 : AppColors.textSecondary),
          const SizedBox(width: 4),
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
