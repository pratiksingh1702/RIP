import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:rip_app/core/design/app_colors.dart';
import 'package:rip_app/data/models/message.dart';
import 'package:rip_app/utils/date_formatter.dart';

import '../../providers/chat_provider.dart';
import '../../providers/project_provider.dart';
import '../../providers/settings_provider.dart';
import '../overlays/add_repo_sheet.dart';
import 'project_list.dart';

class AppDrawer extends ConsumerWidget {
  const AppDrawer({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final themeMode = ref.watch(themeModeProvider);
    final messages = ref.watch(chatProvider);
    final recentMessages = _recentMessages(messages);

    return Drawer(
      width: MediaQuery.sizeOf(context).width * 0.82,
      backgroundColor: Theme.of(context).scaffoldBackgroundColor,
      elevation: 0,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.only(
          topRight: Radius.circular(20),
          bottomRight: Radius.circular(20),
        ),
      ),
      child: SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(10, 10, 10, 12),
          child: Column(
            children: [
              const _DrawerHeaderCompact(),
              const SizedBox(height: 8),
              Row(
                children: [
                  Expanded(
                    child: _CompactAction(
                      icon: Icons.add_rounded,
                      label: 'Add repo',
                      onTap: () {
                        HapticFeedback.selectionClick();
                        showModalBottomSheet(
                          context: context,
                          isScrollControlled: true,
                          backgroundColor: Colors.transparent,
                          builder: (context) => const AddRepoSheet(),
                        );
                      },
                    ),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: _CompactAction(
                      icon: Icons.folder_open_rounded,
                      label: 'Projects',
                      onTap: () {
                        HapticFeedback.selectionClick();
                        ref.invalidate(projectListProvider);
                        showDialog(
                          context: context,
                          builder: (context) => const Dialog(
                            backgroundColor: Colors.transparent,
                            insetPadding: EdgeInsets.all(18),
                            child: SizedBox(height: 440, child: ProjectList()),
                          ),
                        );
                      },
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 10),
              Expanded(
                child: ListView(
                  padding: EdgeInsets.zero,
                  children: [
                    if (recentMessages.isNotEmpty)
                      _CompactSection(
                        title: 'Recent',
                        children: [
                          for (final msg in recentMessages)
                            _CompactRow(
                              icon: msg.isUser
                                  ? Icons.person_outline_rounded
                                  : Icons.bolt_rounded,
                              title: msg.content,
                              subtitle: DateFormatter.formatTime(msg.timestamp),
                              onTap: () => Navigator.pop(context),
                            ),
                        ],
                      ),
                    _CompactSection(
                      title: 'Tools',
                      children: [
                        _CompactRow(
                          icon: Icons.history_rounded,
                          title: 'Clear chat',
                          subtitle: 'Reset current conversation',
                          onTap: () async {
                            HapticFeedback.mediumImpact();
                            await ref.read(chatProvider.notifier).clearChat();
                            if (context.mounted) Navigator.pop(context);
                          },
                        ),
                        const _CompactRow(
                          icon: Icons.memory_rounded,
                          title: 'Memory',
                          subtitle: 'Workspace context',
                        ),
                      ],
                    ),
                    _CompactSection(
                      title: 'Theme',
                      children: [
                        _ThemeRow(
                          label: 'Light',
                          selected: themeMode == ThemeMode.light,
                          onTap: () => ref
                              .read(settingsNotifierProvider.notifier)
                              .saveThemeMode(ThemeMode.light),
                        ),
                        _ThemeRow(
                          label: 'Dark',
                          selected: themeMode == ThemeMode.dark,
                          onTap: () => ref
                              .read(settingsNotifierProvider.notifier)
                              .saveThemeMode(ThemeMode.dark),
                        ),
                        _ThemeRow(
                          label: 'System',
                          selected: themeMode == ThemeMode.system,
                          onTap: () => ref
                              .read(settingsNotifierProvider.notifier)
                              .saveThemeMode(ThemeMode.system),
                        ),
                      ],
                    ),
                    _CompactSection(
                      title: 'Settings',
                      children: [
                        _CompactRow(
                          icon: Icons.tune_rounded,
                          title: 'Server settings',
                          subtitle: 'Connection and API key',
                          onTap: () {
                            HapticFeedback.selectionClick();
                            Navigator.pop(context);
                            context.push('/setup');
                          },
                        ),
                        const _CompactRow(
                          icon: Icons.info_outline_rounded,
                          title: 'About RIP',
                          subtitle: 'Repository intelligence',
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  List<Message> _recentMessages(List<Message> messages) {
    return messages
        .where((message) => message.content.trim().isNotEmpty)
        .toList()
        .reversed
        .take(4)
        .toList();
  }
}

class _DrawerHeaderCompact extends StatelessWidget {
  const _DrawerHeaderCompact();

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    return Container(
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: colorScheme.surface,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: colorScheme.outline.withValues(alpha: 0.6)),
      ),
      child: Row(
        children: [
          const SizedBox(
            width: 36,
            height: 36,
            child: DecoratedBox(
              decoration: BoxDecoration(
                color: AppColors.primary,
                borderRadius: BorderRadius.all(Radius.circular(14)),
              ),
              child: Icon(Icons.auto_awesome_rounded, color: Colors.white),
            ),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'RIP',
                  style: TextStyle(
                    color: colorScheme.onSurface,
                    fontSize: 20,
                    fontWeight: FontWeight.w800,
                  ),
                ),
                Text(
                  'AI workspace',
                  style: TextStyle(
                    color: colorScheme.onSurfaceVariant,
                    fontSize: 12,
                    fontWeight: FontWeight.w500,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _CompactAction extends StatelessWidget {
  const _CompactAction({
    required this.icon,
    required this.label,
    required this.onTap,
  });

  final IconData icon;
  final String label;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    return Material(
      color: colorScheme.surface,
      borderRadius: BorderRadius.circular(16),
      child: InkWell(
        borderRadius: BorderRadius.circular(16),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 10),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(icon, color: AppColors.primary, size: 18),
              const SizedBox(width: 7),
              Flexible(
                child: Text(
                  label,
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(
                    color: colorScheme.onSurface,
                    fontSize: 13,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _CompactSection extends StatelessWidget {
  const _CompactSection({required this.title, required this.children});

  final String title;
  final List<Widget> children;

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(4, 0, 4, 5),
            child: Text(
              title,
              style: TextStyle(
                color: colorScheme.onSurfaceVariant.withValues(alpha: 0.9),
                fontSize: 11,
                fontWeight: FontWeight.w800,
                letterSpacing: 0,
              ),
            ),
          ),
          DecoratedBox(
            decoration: BoxDecoration(
              color: colorScheme.surface,
              borderRadius: BorderRadius.circular(16),
              border: Border.all(color: colorScheme.outline.withValues(alpha: 0.55)),
            ),
            child: Column(children: children),
          ),
        ],
      ),
    );
  }
}

class _CompactRow extends StatelessWidget {
  const _CompactRow({
    required this.icon,
    required this.title,
    required this.subtitle,
    this.onTap,
  });

  final IconData icon;
  final String title;
  final String subtitle;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
          child: Row(
            children: [
              Icon(icon, color: colorScheme.onSurfaceVariant, size: 18),
              const SizedBox(width: 10),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      title,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: TextStyle(
                        color: colorScheme.onSurface,
                        fontSize: 13,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    const SizedBox(height: 1),
                    Text(
                      subtitle,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: TextStyle(
                        color: colorScheme.onSurfaceVariant.withValues(alpha: 0.8),
                        fontSize: 11,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _ThemeRow extends StatelessWidget {
  const _ThemeRow({
    required this.label,
    required this.selected,
    required this.onTap,
  });

  final String label;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return _CompactRow(
      icon: selected ? Icons.radio_button_checked : Icons.radio_button_off,
      title: label,
      subtitle: selected ? 'Selected' : 'Theme mode',
      onTap: () {
        HapticFeedback.selectionClick();
        onTap();
      },
    );
  }
}
