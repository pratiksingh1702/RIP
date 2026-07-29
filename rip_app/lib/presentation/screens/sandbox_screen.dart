import 'dart:ui';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../data/models/sandbox.dart';
import '../providers/sandbox_provider.dart';
import '../widgets/sandbox/terminal_view.dart';
import '../widgets/sandbox/environment_picker.dart';
import '../widgets/sandbox/file_browser.dart';
import '../widgets/sidebar/app_drawer.dart';
import '../widgets/chat/supervisor_chat_sheet.dart';

class SandboxScreen extends ConsumerStatefulWidget {
  final String? projectId;
  const SandboxScreen({super.key, this.projectId});

  @override
  ConsumerState<SandboxScreen> createState() => _SandboxScreenState();
}

class _SandboxScreenState extends ConsumerState<SandboxScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _initializeSandboxes();
    });
  }

  Future<void> _initializeSandboxes() async {
    final notifier = ref.read(sandboxProvider.notifier);
    final projectId = widget.projectId ?? 'default';
    
    await notifier.loadExistingSandboxes(projectId: projectId);
    
    final state = ref.read(sandboxProvider);
    if (state.activeSandboxes.isEmpty) {
      notifier.createSandbox(projectId, environment: 'python');
    }
  }

  void _createSandbox(SandboxTemplate template) {
    final environment = template.id;
    final projectId = widget.projectId ?? 'default';
    ref.read(sandboxProvider.notifier).createSandbox(projectId, environment: environment);
  }

  void _openEnvSelectorModal() {
    HapticFeedback.selectionClick();
    showModalBottomSheet(
      context: context,
      backgroundColor: Colors.transparent,
      isScrollControlled: true,
      builder: (context) => DraggableScrollableSheet(
        initialChildSize: 0.75,
        maxChildSize: 0.9,
        minChildSize: 0.5,
        builder: (context, scrollController) => ClipRRect(
          borderRadius: const BorderRadius.vertical(top: Radius.circular(24)),
          child: Container(
            color: const Color(0xFF0F0F23),
            child: EnvironmentPicker(
              onSelect: (template) {
                Navigator.pop(context);
                _createSandbox(template);
              },
            ),
          ),
        ),
      ),
    );
  }

  void _openFilesModal() {
    HapticFeedback.selectionClick();
    showModalBottomSheet(
      context: context,
      backgroundColor: Colors.transparent,
      isScrollControlled: true,
      builder: (context) => DraggableScrollableSheet(
        initialChildSize: 0.6,
        maxChildSize: 0.85,
        minChildSize: 0.4,
        builder: (context, scrollController) => ClipRRect(
          borderRadius: const BorderRadius.vertical(top: Radius.circular(24)),
          child: Container(
            color: const Color(0xFF13132B),
            padding: const EdgeInsets.all(20),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Center(
                  child: Container(
                    width: 40,
                    height: 4,
                    decoration: BoxDecoration(
                      color: Colors.white24,
                      borderRadius: BorderRadius.circular(2),
                    ),
                  ),
                ),
                const SizedBox(height: 16),
                const Row(
                  children: [
                    Icon(Icons.folder_copy_rounded, color: Color(0xFF818CF8), size: 20),
                    SizedBox(width: 10),
                    Text(
                      'Workspace Files Inspector',
                      style: TextStyle(
                        color: Colors.white,
                        fontSize: 16,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 16),
                Expanded(
                  child: SandboxFileBrowser(
                    files: const [
                      {'name': 'workspace', 'path': '/workspace', 'is_directory': true},
                      {'name': 'main.py', 'path': '/workspace/main.py', 'is_directory': false},
                      {'name': 'requirements.txt', 'path': '/workspace/requirements.txt', 'is_directory': false},
                      {'name': 'logs', 'path': '/workspace/logs', 'is_directory': true},
                    ],
                    onFileTap: (path) {
                      Navigator.pop(context);
                      ref.read(sandboxProvider.notifier).sendCommand('cat $path');
                    },
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  void _openEditSandboxModal(SandboxSession activeSession) {
    HapticFeedback.selectionClick();
    final nameController = TextEditingController(text: activeSession.sandbox.name);
    final descController = TextEditingController(text: activeSession.sandbox.description);

    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: const Color(0xFF13132B),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        title: const Text('Edit Sandbox Details', style: TextStyle(color: Colors.white, fontSize: 16)),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(
              controller: nameController,
              style: const TextStyle(color: Colors.white),
              decoration: InputDecoration(
                labelText: 'Name',
                labelStyle: const TextStyle(color: Colors.white54),
                enabledBorder: UnderlineInputBorder(borderSide: BorderSide(color: Colors.white.withValues(alpha: 0.2))),
                focusedBorder: const UnderlineInputBorder(borderSide: BorderSide(color: Color(0xFF818CF8))),
              ),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: descController,
              style: const TextStyle(color: Colors.white),
              maxLines: 3,
              decoration: InputDecoration(
                labelText: 'Description (Bio)',
                labelStyle: const TextStyle(color: Colors.white54),
                enabledBorder: UnderlineInputBorder(borderSide: BorderSide(color: Colors.white.withValues(alpha: 0.2))),
                focusedBorder: const UnderlineInputBorder(borderSide: BorderSide(color: Color(0xFF818CF8))),
              ),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel', style: TextStyle(color: Colors.white54)),
          ),
          TextButton(
            onPressed: () {
              ref.read(sandboxProvider.notifier).updateSandbox(
                activeSession.sandbox.id,
                name: nameController.text.trim().isEmpty ? null : nameController.text.trim(),
                description: descController.text.trim().isEmpty ? null : descController.text.trim(),
              );
              Navigator.pop(context);
            },
            child: const Text('Save', style: TextStyle(color: Color(0xFF10B981))),
          ),
        ],
      ),
    );
  }

  void _showCornerInfoDialog(BuildContext context, SandboxSession? activeSession, int totalActive) {
    HapticFeedback.selectionClick();
    final env = activeSession?.sandbox.environment.toUpperCase() ?? 'NONE';
    final id = activeSession?.sandbox.id ?? 'N/A';
    final status = activeSession?.isConnected == true ? 'RUNNING' : 'STANDBY';

    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: const Color(0xFF13132B),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(20),
          side: BorderSide(color: Colors.white.withValues(alpha: 0.12)),
        ),
        title: const Row(
          children: [
            Icon(Icons.dns_rounded, color: Color(0xFF10B981), size: 22),
            SizedBox(width: 10),
            Text(
              'Container Metrics',
              style: TextStyle(color: Colors.white, fontSize: 16, fontWeight: FontWeight.bold),
            ),
          ],
        ),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _InfoRow(label: 'Environment', value: env),
            _InfoRow(label: 'Session ID', value: id),
            _InfoRow(label: 'Status', value: status, valueColor: const Color(0xFF10B981)),
            _InfoRow(label: 'Active Containers', value: '$totalActive running'),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Close', style: TextStyle(color: Color(0xFF818CF8))),
          ),
        ],
      ),
    );
  }

  void _confirmRestartContainer(BuildContext context, WidgetRef ref, SandboxSession? activeSession) {
    if (activeSession == null) return;
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
        title: const Row(
          children: [
            Icon(Icons.restart_alt_rounded, color: Color(0xFF6366F1)),
            SizedBox(width: 8),
            Text('Restart Container?'),
          ],
        ),
        content: Text('Reboot container "${activeSession.sandbox.name ?? activeSession.sandbox.id}" and reconnect terminal streaming?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            style: ElevatedButton.styleFrom(
              backgroundColor: const Color(0xFF6366F1),
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
            ),
            onPressed: () {
              Navigator.pop(ctx);
              ref.read(sandboxProvider.notifier).restartSandbox(activeSession.sandbox.id);
            },
            child: const Text('Restart', style: TextStyle(color: Colors.white)),
          ),
        ],
      ),
    );
  }

  void _copyLogs(BuildContext context, List<TerminalOutput> outputs) {
    final fullLog = outputs.map((o) => '${o.type}: ${o.command} ${o.output}').join('\n');
    Clipboard.setData(ClipboardData(text: fullLog));
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: const Row(
          children: [
            Icon(Icons.check_circle_outline, color: Color(0xFF10B981), size: 18),
            SizedBox(width: 8),
            Text('Terminal logs copied to clipboard'),
          ],
        ),
        behavior: SnackBarBehavior.floating,
        backgroundColor: const Color(0xFF1E1E3F),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(sandboxProvider);
    final activeSessions = state.activeSandboxes;
    final activeSession = state.activeSession;
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final bgColor = isDark ? Colors.black : Theme.of(context).scaffoldBackgroundColor;

    return Scaffold(
      drawer: const AppDrawer(),
      drawerEdgeDragWidth: MediaQuery.sizeOf(context).width * 0.4,
      backgroundColor: bgColor,
      body: Builder(
        builder: (context) {
          return GestureDetector(
            onHorizontalDragEnd: (details) {
              if ((details.primaryVelocity ?? 0) > 250) {
                HapticFeedback.selectionClick();
                Scaffold.of(context).openDrawer();
              }
            },
            child: Stack(
              children: [
                // Terminal Stream Area
                Positioned.fill(
                  child: const TerminalView(),
                ),

                // Floating Glassmorphic Top Bar
                Positioned(
                  top: 0,
                  left: 0,
                  right: 0,
                  child: _FloatingSandboxHeader(
                    activeSession: activeSession,
                    activeSessions: activeSessions,
                    onMenuTap: () {
                      HapticFeedback.selectionClick();
                      Scaffold.of(context).openDrawer();
                    },
                    onNewSandboxTap: _openEnvSelectorModal,
                    onEditSandboxTap: activeSession != null ? () => _openEditSandboxModal(activeSession) : null,
                    onFilesTap: _openFilesModal,
                    onSupervisorTap: () {
                      HapticFeedback.selectionClick();
                      final taskId = activeSession?.sandbox.id ?? 'sandbox-terminal';
                      SupervisorChatSheet.show(context, taskId);
                    },
                    onInfoTap: () => _showCornerInfoDialog(context, activeSession, activeSessions.length),
                  ),
                ),
                
                // Floating Merged Action Icons (Copy & Clear)
                Positioned(
                  top: MediaQuery.paddingOf(context).top + 64, // just below the floating header
                  right: 16,
                  child: ClipRRect(
                    borderRadius: BorderRadius.circular(16),
                    child: BackdropFilter(
                      filter: ImageFilter.blur(sigmaX: 12, sigmaY: 12),
                      child: Container(
                        height: 42,
                        padding: const EdgeInsets.symmetric(horizontal: 4),
                        decoration: BoxDecoration(
                          color: isDark ? Colors.white.withValues(alpha: 0.08) : Colors.black.withValues(alpha: 0.05),
                          borderRadius: BorderRadius.circular(16),
                          border: Border.all(
                            color: isDark ? Colors.white.withValues(alpha: 0.12) : Colors.black.withValues(alpha: 0.1),
                          ),
                        ),
                        child: Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            IconButton(
                              icon: Icon(Icons.copy_rounded, color: isDark ? Colors.white : Colors.black87, size: 18),
                              tooltip: 'Copy Logs',
                              onPressed: () => _copyLogs(context, state.terminalOutputs),
                              constraints: const BoxConstraints(minWidth: 34, minHeight: 34),
                              padding: EdgeInsets.zero,
                            ),
                            Container(
                              width: 1,
                              height: 16,
                              color: isDark ? Colors.white12 : Colors.black12,
                            ),
                            IconButton(
                              icon: Icon(Icons.refresh_rounded, color: isDark ? Colors.white : Colors.black87, size: 18),
                              tooltip: 'Restart Container',
                              onPressed: () => _confirmRestartContainer(context, ref, activeSession),
                              constraints: const BoxConstraints(minWidth: 34, minHeight: 34),
                              padding: EdgeInsets.zero,
                            ),
                            Container(
                              width: 1,
                              height: 16,
                              color: isDark ? Colors.white12 : Colors.black12,
                            ),
                            IconButton(
                              icon: Icon(Icons.delete_outline_rounded, color: isDark ? Colors.white : Colors.black87, size: 18),
                              tooltip: 'Clear Terminal',
                              onPressed: () => ref.read(sandboxProvider.notifier).clearTerminal(),
                              constraints: const BoxConstraints(minWidth: 34, minHeight: 34),
                              padding: EdgeInsets.zero,
                            ),
                          ],
                        ),
                      ),
                    ),
                  ),
                ),
              ],
            ),
          );
        },
      ),
    );
  }
}

class _GlassIconButton extends StatelessWidget {
  final IconData icon;
  final String tooltip;
  final VoidCallback onPressed;
  final Color? iconColor;

  const _GlassIconButton({
    required this.icon,
    required this.tooltip,
    required this.onPressed,
    this.iconColor,
  });

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final defaultColor = isDark ? Colors.white : Colors.black87;

    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onPressed,
        borderRadius: BorderRadius.circular(16),
        child: ClipRRect(
          borderRadius: BorderRadius.circular(16),
          child: BackdropFilter(
            filter: ImageFilter.blur(sigmaX: 12, sigmaY: 12),
            child: Container(
              width: 42,
              height: 42,
              decoration: BoxDecoration(
                color: isDark ? Colors.white.withValues(alpha: 0.08) : Colors.black.withValues(alpha: 0.05),
                borderRadius: BorderRadius.circular(16),
                border: Border.all(color: isDark ? Colors.white.withValues(alpha: 0.12) : Colors.black.withValues(alpha: 0.1)),
              ),
              child: Icon(icon, color: iconColor ?? defaultColor, size: 20),
            ),
          ),
        ),
      ),
    );
  }
}

class _FloatingSandboxHeader extends ConsumerWidget {
  final SandboxSession? activeSession;
  final List<SandboxSession> activeSessions;
  final VoidCallback onMenuTap;
  final VoidCallback onNewSandboxTap;
  final VoidCallback? onEditSandboxTap;
  final VoidCallback onFilesTap;
  final VoidCallback onSupervisorTap;
  final VoidCallback onInfoTap;

  const _FloatingSandboxHeader({
    required this.activeSession,
    required this.activeSessions,
    required this.onMenuTap,
    required this.onNewSandboxTap,
    required this.onEditSandboxTap,
    required this.onFilesTap,
    required this.onSupervisorTap,
    required this.onInfoTap,
  });

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final top = MediaQuery.paddingOf(context).top;

    return Container(
      padding: EdgeInsets.fromLTRB(14, top + 8, 14, 8),
      child: Row(
        children: [
          _GlassIconButton(
            icon: Icons.menu_rounded,
            tooltip: 'Menu',
            onPressed: onMenuTap,
          ),
          const SizedBox(width: 8),
          Expanded(
            child: _HeaderSandboxDropdownSelector(
              activeSession: activeSession,
              activeSessions: activeSessions,
              onNewSandboxTap: onNewSandboxTap,
              onEditSandboxTap: onEditSandboxTap,
            ),
          ),
          const SizedBox(width: 8),
          _GlassIconButton(
            icon: Icons.psychology_rounded,
            tooltip: 'Ask Supervisor',
            iconColor: const Color(0xFF06B6D4), // Cyan Accent
            onPressed: onSupervisorTap,
          ),
          const SizedBox(width: 8),
          _GlassIconButton(
            icon: Icons.folder_open_rounded,
            tooltip: 'Files',
            onPressed: onFilesTap,
          ),
          const SizedBox(width: 8),

          // Corner Info Badge
          Material(
            color: Colors.transparent,
            child: InkWell(
              onTap: onInfoTap,
              borderRadius: BorderRadius.circular(16),
              child: ClipRRect(
                borderRadius: BorderRadius.circular(16),
                child: BackdropFilter(
                  filter: ImageFilter.blur(sigmaX: 12, sigmaY: 12),
                  child: Container(
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
                    height: 42,
                    decoration: BoxDecoration(
                      color: Theme.of(context).brightness == Brightness.dark ? Colors.white.withValues(alpha: 0.08) : Colors.black.withValues(alpha: 0.05),
                      borderRadius: BorderRadius.circular(16),
                      border: Border.all(color: Theme.of(context).brightness == Brightness.dark ? Colors.white.withValues(alpha: 0.12) : Colors.black.withValues(alpha: 0.1)),
                    ),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Container(
                          width: 8,
                          height: 8,
                          decoration: BoxDecoration(
                            shape: BoxShape.circle,
                            color: activeSessions.isNotEmpty
                                ? const Color(0xFF10B981)
                                : Colors.amber,
                            boxShadow: [
                              BoxShadow(
                                color: (activeSessions.isNotEmpty
                                        ? const Color(0xFF10B981)
                                        : Colors.amber)
                                    .withValues(alpha: 0.8),
                                blurRadius: 4,
                              ),
                            ],
                          ),
                        ),
                        const SizedBox(width: 6),
                        Text(
                          '${activeSessions.length} Active',
                          style: TextStyle(
                            color: Theme.of(context).brightness == Brightness.dark ? Colors.white70 : Colors.black87,
                            fontSize: 11,
                            fontWeight: FontWeight.bold,
                            fontFamily: 'monospace',
                          ),
                        ),
                      ],
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

class _HeaderSandboxDropdownSelector extends ConsumerWidget {
  final SandboxSession? activeSession;
  final List<SandboxSession> activeSessions;
  final VoidCallback onNewSandboxTap;
  final VoidCallback? onEditSandboxTap;

  const _HeaderSandboxDropdownSelector({
    required this.activeSession,
    required this.activeSessions,
    required this.onNewSandboxTap,
    required this.onEditSandboxTap,
  });

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final activeId = activeSession?.sandbox.id;
    final currentEnv = activeSession?.sandbox.name?.isNotEmpty == true 
        ? activeSession!.sandbox.name! 
        : activeSession?.sandbox.environment.toUpperCase() ?? 'NO SANDBOX';

    final isDark = Theme.of(context).brightness == Brightness.dark;

    return PopupMenuButton<String>(
      tooltip: 'Switch Sandbox Environment',
      offset: const Offset(0, 48),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(16),
        side: BorderSide(
          color: isDark ? Colors.white.withValues(alpha: 0.15) : Colors.black.withValues(alpha: 0.1),
        ),
      ),
      color: isDark ? const Color(0xFF13132B).withValues(alpha: 0.96) : Colors.white.withValues(alpha: 0.96),
      elevation: 8,
      onSelected: (val) {
        HapticFeedback.selectionClick();
        if (val == '__new__') {
          onNewSandboxTap();
        } else if (val == '__edit__') {
          onEditSandboxTap?.call();
        } else if (val == '__restart__') {
          if (activeSession != null) {
            ref.read(sandboxProvider.notifier).restartSandbox(activeSession!.sandbox.id);
          }
        } else {
          ref.read(sandboxProvider.notifier).switchActiveSandbox(val);
        }
      },
      itemBuilder: (context) {
        final items = <PopupMenuEntry<String>>[];

        items.add(
          PopupMenuItem<String>(
            enabled: false,
            child: Row(
              children: [
                const Icon(Icons.terminal_rounded, size: 16, color: Color(0xFF818CF8)),
                const SizedBox(width: 8),
                Text(
                  'ACTIVE SANDBOXES',
                  style: TextStyle(
                    fontSize: 10,
                    fontWeight: FontWeight.bold,
                    letterSpacing: 0.8,
                    color: isDark ? Colors.white54 : Colors.black54,
                  ),
                ),
              ],
            ),
          ),
        );
        items.add(const PopupMenuDivider());

        if (activeSessions.isEmpty) {
          items.add(
            PopupMenuItem<String>(
              enabled: false,
              child: Text(
                'No active sandboxes',
                style: TextStyle(
                  color: isDark ? Colors.white38 : Colors.black38,
                  fontSize: 12,
                ),
              ),
            ),
          );
        } else {
          for (final session in activeSessions) {
            final isCurrent = session.sandbox.id == activeId;
            final envName = session.sandbox.name?.isNotEmpty == true
                ? session.sandbox.name!
                : session.sandbox.environment.toUpperCase();

            items.add(
              PopupMenuItem<String>(
                value: session.sandbox.id,
                child: Row(
                  children: [
                    Container(
                      width: 6,
                      height: 6,
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        color: isCurrent
                            ? const Color(0xFF10B981)
                            : (isDark ? Colors.white38 : Colors.black26),
                      ),
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      child: Text(
                        envName,
                        style: TextStyle(
                          color: isCurrent
                              ? (isDark ? Colors.white : Colors.black87)
                              : (isDark ? Colors.white70 : Colors.black54),
                          fontSize: 13,
                          fontWeight: isCurrent ? FontWeight.bold : FontWeight.normal,
                          fontFamily: 'monospace',
                        ),
                      ),
                    ),
                    if (isCurrent)
                      const Icon(Icons.check_rounded, color: Color(0xFF10B981), size: 16),
                  ],
                ),
              ),
            );
          }
        }

        items.add(const PopupMenuDivider());
        if (activeSession != null) {
          items.add(
            PopupMenuItem<String>(
              value: '__edit__',
              child: Row(
                children: [
                  Icon(Icons.edit_rounded, color: isDark ? Colors.white54 : Colors.black54, size: 18),
                  const SizedBox(width: 8),
                  Text(
                    'Edit Current Sandbox...',
                    style: TextStyle(
                      color: isDark ? Colors.white70 : Colors.black87,
                      fontSize: 12,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ],
              ),
            ),
          );
          items.add(
            PopupMenuItem<String>(
              value: '__restart__',
              child: Row(
                children: [
                  Icon(Icons.restart_alt_rounded, color: isDark ? Colors.white54 : Colors.black54, size: 18),
                  const SizedBox(width: 8),
                  Text(
                    'Restart Container...',
                    style: TextStyle(
                      color: isDark ? Colors.white70 : Colors.black87,
                      fontSize: 12,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ],
              ),
            ),
          );
        }
        items.add(
          PopupMenuItem<String>(
            value: '__new__',
            child: Row(
              children: [
                const Icon(Icons.add_rounded, color: Color(0xFF818CF8), size: 18),
                const SizedBox(width: 8),
                Text(
                  'Create New Sandbox...',
                  style: TextStyle(
                    color: isDark ? const Color(0xFF818CF8) : const Color(0xFF4F46E5),
                    fontSize: 12,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ],
            ),
          ),
        );

        return items;
      },
      child: Builder(
        builder: (context) {
          final isDark = Theme.of(context).brightness == Brightness.dark;
          return ClipRRect(
            borderRadius: BorderRadius.circular(16),
            child: BackdropFilter(
              filter: ImageFilter.blur(sigmaX: 12, sigmaY: 12),
              child: Container(
                height: 42,
                padding: const EdgeInsets.symmetric(horizontal: 12),
                decoration: BoxDecoration(
                  color: isDark ? Colors.white.withValues(alpha: 0.08) : Colors.black.withValues(alpha: 0.05),
                  borderRadius: BorderRadius.circular(16),
                  border: Border.all(
                    color: isDark ? Colors.white.withValues(alpha: 0.12) : Colors.black.withValues(alpha: 0.1),
                    width: 1,
                  ),
                ),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    const Icon(Icons.terminal_rounded, size: 16, color: Color(0xFF10B981)),
                    const SizedBox(width: 8),
                    Flexible(
                      child: Text(
                        currentEnv,
                        style: TextStyle(
                          color: isDark ? Colors.white : Colors.black87,
                          fontSize: 13,
                          fontWeight: FontWeight.bold,
                          fontFamily: 'monospace',
                        ),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                    const SizedBox(width: 6),
                    Icon(
                      Icons.keyboard_arrow_down_rounded,
                      color: isDark ? Colors.white70 : Colors.black54,
                      size: 18,
                    ),
                  ],
                ),
              ),
            ),
          );
        },
      ),
    );
  }
}

class _InfoRow extends StatelessWidget {
  final String label;
  final String value;
  final Color? valueColor;

  const _InfoRow({
    required this.label,
    required this.value,
    this.valueColor,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label, style: const TextStyle(color: Colors.white54, fontSize: 12)),
          Text(
            value,
            style: TextStyle(
              color: valueColor ?? Colors.white,
              fontSize: 12,
              fontWeight: FontWeight.bold,
              fontFamily: 'monospace',
            ),
          ),
        ],
      ),
    );
  }
}