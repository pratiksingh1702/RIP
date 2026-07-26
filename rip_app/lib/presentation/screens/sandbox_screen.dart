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
    final state = ref.read(sandboxProvider);
    if (state.activeSandboxes.isEmpty && state.sandbox == null) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        _autoCreateDefaultSandbox();
      });
    }
  }

  void _autoCreateDefaultSandbox() {
    final projectId = widget.projectId ?? 'default';
    ref.read(sandboxProvider.notifier).createSandbox(projectId, environment: 'python');
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

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(sandboxProvider);
    final activeSessions = state.activeSandboxes;
    final activeSession = state.activeSession;

    return Scaffold(
      drawer: const AppDrawer(),
      drawerEdgeDragWidth: MediaQuery.sizeOf(context).width * 0.4,
      backgroundColor: const Color(0xFF0A0A16),
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
                  child: Padding(
                    padding: EdgeInsets.only(top: MediaQuery.paddingOf(context).top + 64),
                    child: const TerminalView(),
                  ),
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
                    onFilesTap: _openFilesModal,
                    onInfoTap: () => _showCornerInfoDialog(context, activeSession, activeSessions.length),
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

  const _GlassIconButton({
    required this.icon,
    required this.tooltip,
    required this.onPressed,
  });

  @override
  Widget build(BuildContext context) {
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
                color: Colors.white.withValues(alpha: 0.08),
                borderRadius: BorderRadius.circular(16),
                border: Border.all(color: Colors.white.withValues(alpha: 0.12)),
              ),
              child: Icon(icon, color: Colors.white, size: 20),
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
  final VoidCallback onFilesTap;
  final VoidCallback onInfoTap;

  const _FloatingSandboxHeader({
    required this.activeSession,
    required this.activeSessions,
    required this.onMenuTap,
    required this.onNewSandboxTap,
    required this.onFilesTap,
    required this.onInfoTap,
  });

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final top = MediaQuery.paddingOf(context).top;

    return Container(
      padding: EdgeInsets.fromLTRB(14, top + 8, 14, 8),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [
            const Color(0xFF0A0A16).withValues(alpha: 0.95),
            const Color(0xFF0A0A16).withValues(alpha: 0.6),
            Colors.transparent,
          ],
          stops: const [0.0, 0.7, 1.0],
        ),
      ),
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
            ),
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
                      color: Colors.white.withValues(alpha: 0.08),
                      borderRadius: BorderRadius.circular(16),
                      border: Border.all(color: Colors.white.withValues(alpha: 0.12)),
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
                          style: const TextStyle(
                            color: Colors.white70,
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

  const _HeaderSandboxDropdownSelector({
    required this.activeSession,
    required this.activeSessions,
    required this.onNewSandboxTap,
  });

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final activeId = activeSession?.sandbox.id;
    final currentEnv = activeSession?.sandbox.environment.toUpperCase() ?? 'NO SANDBOX';

    return PopupMenuButton<String>(
      tooltip: 'Switch Sandbox Environment',
      offset: const Offset(0, 48),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(18),
        side: BorderSide(color: Colors.white.withValues(alpha: 0.15)),
      ),
      color: const Color(0xFF13132B).withValues(alpha: 0.96),
      elevation: 8,
      onSelected: (val) {
        HapticFeedback.selectionClick();
        if (val == '__new__') {
          onNewSandboxTap();
        } else {
          ref.read(sandboxProvider.notifier).switchActiveSandbox(val);
        }
      },
      itemBuilder: (context) {
        final items = <PopupMenuEntry<String>>[];

        items.add(
          const PopupMenuItem<String>(
            enabled: false,
            child: Row(
              children: [
                Icon(Icons.terminal_rounded, size: 16, color: Color(0xFF818CF8)),
                SizedBox(width: 8),
                Text(
                  'ACTIVE SANDBOXES',
                  style: TextStyle(
                    fontSize: 10,
                    fontWeight: FontWeight.bold,
                    letterSpacing: 0.8,
                    color: Colors.white54,
                  ),
                ),
              ],
            ),
          ),
        );
        items.add(const PopupMenuDivider());

        if (activeSessions.isEmpty) {
          items.add(
            const PopupMenuItem<String>(
              enabled: false,
              child: Text('No active sandboxes', style: TextStyle(color: Colors.white38, fontSize: 12)),
            ),
          );
        } else {
          for (final session in activeSessions) {
            final isCurrent = session.sandbox.id == activeId;
            final envName = session.sandbox.environment.toUpperCase();

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
                        color: isCurrent ? const Color(0xFF10B981) : Colors.white38,
                      ),
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      child: Text(
                        envName,
                        style: TextStyle(
                          color: isCurrent ? Colors.white : Colors.white70,
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
        items.add(
          const PopupMenuItem<String>(
            value: '__new__',
            child: Row(
              children: [
                Icon(Icons.add_rounded, color: Color(0xFF818CF8), size: 18),
                SizedBox(width: 8),
                Text(
                  'Create New Sandbox...',
                  style: TextStyle(
                    color: Color(0xFF818CF8),
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
      child: ClipRRect(
        borderRadius: BorderRadius.circular(20),
        child: BackdropFilter(
          filter: ImageFilter.blur(sigmaX: 12, sigmaY: 12),
          child: Container(
            height: 42,
            padding: const EdgeInsets.symmetric(horizontal: 14),
            decoration: BoxDecoration(
              color: Colors.white.withValues(alpha: 0.08),
              borderRadius: BorderRadius.circular(20),
              border: Border.all(
                color: Colors.white.withValues(alpha: 0.15),
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
                    style: const TextStyle(
                      color: Colors.white,
                      fontSize: 13,
                      fontWeight: FontWeight.bold,
                      fontFamily: 'monospace',
                    ),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
                const SizedBox(width: 6),
                const Icon(
                  Icons.keyboard_arrow_down_rounded,
                  color: Colors.white70,
                  size: 18,
                ),
              ],
            ),
          ),
        ),
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